
"""
Created on Thu May 21 09:15:23 2026

@author: resurrection
"""

import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime


DATU_MAPE =r"C:\Users\bak\sample3_30s"

VILNA_GARUMS_MIN = 450
VILNA_GARUMS_MAX = 800

NOKLUSETAIS_SOLIS_SEK = 15


SAKUMA_SPEKTRU_SKAITS = 3

# "30s" -  UV 30 sekundes, atkrāsošanās 15 minūtes
# "1min" - UV 1 minūte, atkrāsošanās 25 minūtes
# "3min" - UV 3 minūtes, atkrāsošanās 35 minūtes
REZIMS = "30sZ"

# Ciklu skaitsZ
CIKLU_SKAITS = 10

# arduino režimi

REZIMI = {
    "30s": {
        "uv_ieslegts_s": 30,
        "uv_izslegts_s": 15 * 60
    },
    "1min": {
        "uv_ieslegts_s": 60,
        "uv_izslegts_s": 25 * 60
    },
    "3min": {
        "uv_ieslegts_s": 3 * 60,
        "uv_izslegts_s": 35 * 60
    }
}



def nolasit_ocean_optics_txt(faila_cels):
    """
    Nolasa Ocean Optics txt failu.

    Atgriež:
    - mērījuma laiku no Date rindas;
    - spektru ar kolonnām wavelength_nm un intensity.
    """

    with open(faila_cels, "r", encoding="utf-8", errors="ignore") as f:
        rindas = f.readlines()

    merijuma_laiks = None

    for rinda in rindas:
        if rinda.startswith("Date:"):
            datuma_teksts = rinda.replace("Date:", "").strip()

        
            dalas = datuma_teksts.split()

            if len(dalas) >= 6:
                attiritais_datums = " ".join([
                    dalas[0],
                    dalas[1],
                    dalas[2],
                    dalas[3],
                    dalas[5]
                ])

                try:
                    merijuma_laiks = datetime.strptime(
                        attiritais_datums,
                        "%a %b %d %H:%M:%S %Y"
                    )
                except ValueError:
                    merijuma_laiks = None

    sakuma_indekss = None

    for i, rinda in enumerate(rindas):
        if "Begin Spectral Data" in rinda:
            sakuma_indekss = i + 1
            break

    if sakuma_indekss is None:
        raise ValueError(f"Failā nav atrasti spektrālie dati: {faila_cels}")

    vilna_garumi = []
    intensitates = []

    for rinda in rindas[sakuma_indekss:]:
        dalas = rinda.strip().replace(",", ".").split()

        if len(dalas) >= 2:
            try:
                vilna_garums = float(dalas[0])
                intensitate = float(dalas[1])

                vilna_garumi.append(vilna_garums)
                intensitates.append(intensitate)

            except ValueError:
                continue

    spektrs = pd.DataFrame({
        "wavelength_nm": vilna_garumi,
        "intensity": intensitates
    })

    return merijuma_laiks, spektrs


def nolasit_visus_spektrus(mape):
    """
    Nolasa visus txt failus mapē un sakārto tos pēc mērījuma laika.
    Ja Date rinda nav nolasāma, tiek izmantots faila izveidošanas laiks.
    """

    faili = glob.glob(os.path.join(mape, "*.txt"))

    if len(faili) == 0:
        raise FileNotFoundError("Mapē nav atrasti txt faili.")

    ieraksti = []

    for fails in faili:
        merijuma_laiks, spektrs = nolasit_ocean_optics_txt(fails)

        ieraksti.append({
            "fails": os.path.basename(fails),
            "faila_cels": fails,
            "merijuma_laiks": merijuma_laiks,
            "izveidosanas_laiks": datetime.fromtimestamp(os.path.getctime(fails)),
            "modificesanas_laiks": datetime.fromtimestamp(os.path.getmtime(fails)),
            "spektrs": spektrs
        })

    dati = pd.DataFrame(ieraksti)


    if dati["merijuma_laiks"].notna().all():
        dati = dati.sort_values("merijuma_laiks").reset_index(drop=True)
        t0 = dati["merijuma_laiks"].iloc[0]
        dati["laiks_s"] = (dati["merijuma_laiks"] - t0).dt.total_seconds()


    else:
        dati = dati.sort_values("izveidosanas_laiks").reset_index(drop=True)
        t0 = dati["izveidosanas_laiks"].iloc[0]
        dati["laiks_s"] = (dati["izveidosanas_laiks"] - t0).dt.total_seconds()


        if dati["laiks_s"].nunique() <= 1:
            dati["laiks_s"] = dati.index * NOKLUSETAIS_SOLIS_SEK

    dati["laiks_min"] = dati["laiks_s"] / 60

    return dati


def aprekinat_aptumsosanos_no_sakuma_spektra(dati):
    """
    Aprēķina aptumšošanās pakāpi, salīdzinot katru spektru
    ar sākotnējo spektru S0(lambda).

    Katram viļņa garumam:
    D_i(lambda) = (1 - S_i(lambda) / S_0(lambda)) * 100%

    Pēc tam D_i(lambda) tiek vidējots izvēlētajā diapazonā 450--800 nm.
    """

    if len(dati) < SAKUMA_SPEKTRU_SKAITS:
        raise ValueError("Failu skaits ir mazāks nekā sākuma spektru skaits.")

    pirmais_spektrs = dati["spektrs"].iloc[0].copy()

    maska = (
        (pirmais_spektrs["wavelength_nm"] >= VILNA_GARUMS_MIN) &
        (pirmais_spektrs["wavelength_nm"] <= VILNA_GARUMS_MAX)
    )

    vilna_garumi_analizei = pirmais_spektrs.loc[maska, "wavelength_nm"].values


    sakuma_spektri = []

    for i in range(SAKUMA_SPEKTRU_SKAITS):
        spektrs = dati["spektrs"].iloc[i]
        intensitates = spektrs.loc[maska, "intensity"].values
        sakuma_spektri.append(intensitates)

    S0_lambda = np.mean(sakuma_spektri, axis=0)

    rezultati = []
    visi_aptumsosanas_spektri = []

    for i, rinda in dati.iterrows():
        spektrs = rinda["spektrs"]
        Si_lambda = spektrs.loc[maska, "intensity"].values

        # lai izvairītos no dalīšanas ar nulli vai negatīvām vērtībām
        deriga_maska = S0_lambda > 0

        D_lambda = np.full_like(S0_lambda, np.nan, dtype=float)

        D_lambda[deriga_maska] = (
            1 - Si_lambda[deriga_maska] / S0_lambda[deriga_maska]
        ) * 100

        D_lambda_korigets = np.where(D_lambda < 0, 0, D_lambda)

        videja_aptumsosanas_pakape = np.nanmean(D_lambda_korigets)
        medianas_aptumsosanas_pakape = np.nanmedian(D_lambda_korigets)
        max_aptumsosanas_pakape = np.nanmax(D_lambda_korigets)

        videja_intensitate = np.nanmean(Si_lambda)

        rezultati.append({
            "fails": rinda["fails"],
            "merijuma_laiks": rinda["merijuma_laiks"],
            "izveidosanas_laiks": rinda["izveidosanas_laiks"],
            "laiks_s": rinda["laiks_s"],
            "laiks_min": rinda["laiks_min"],
            "videja_intensitate_450_800": videja_intensitate,
            "videja_aptumsosanas_pakape_proc": videja_aptumsosanas_pakape,
            "medianas_aptumsosanas_pakape_proc": medianas_aptumsosanas_pakape,
            "max_aptumsosanas_pakape_proc": max_aptumsosanas_pakape
        })

        # Saglabā visu D(lambda) spektru
        apt_spektrs = pd.DataFrame({
            "wavelength_nm": vilna_garumi_analizei,
            "aptumsosanas_pakape_proc": D_lambda_korigets
        })

        apt_spektrs["fails"] = rinda["fails"]
        apt_spektrs["laiks_min"] = rinda["laiks_min"]

        visi_aptumsosanas_spektri.append(apt_spektrs)

    laika_dati = pd.DataFrame(rezultati)

    aptumsosanas_spektri = pd.concat(
        visi_aptumsosanas_spektri,
        ignore_index=True
    )

    sakuma_spektrs_df = pd.DataFrame({
        "wavelength_nm": vilna_garumi_analizei,
        "S0_lambda": S0_lambda
    })

    return laika_dati, aptumsosanas_spektri, sakuma_spektrs_df

def analizet_ciklus(laika_dati, rezims, ciklu_skaits):
    """
    Aprēķina katra cikla galvenos parametrus:
    - maksimālo aptumšošanās pakāpi;
    - aptumšošanās pakāpi cikla beigās;
    - atlikušā iekrāsojuma līmeni;
    - cikla amplitūdu;
    - vidējo krāsošanās un atkrāsošanās ātrumu.
    """

    uv_ieslegts_s = REZIMI[rezims]["uv_ieslegts_s"]
    uv_izslegts_s = REZIMI[rezims]["uv_izslegts_s"]
    cikla_ilgums_s = uv_ieslegts_s + uv_izslegts_s

    rezultati = []

    for cikls in range(ciklu_skaits):
        cikla_sakums = cikls * cikla_ilgums_s
        uv_beigas = cikla_sakums + uv_ieslegts_s
        cikla_beigas = cikla_sakums + cikla_ilgums_s

        cikla_dati = laika_dati[
            (laika_dati["laiks_s"] >= cikla_sakums) &
            (laika_dati["laiks_s"] < cikla_beigas)
        ]

        uv_dati = laika_dati[
            (laika_dati["laiks_s"] >= cikla_sakums) &
            (laika_dati["laiks_s"] < uv_beigas)
        ]

        atkr_dati = laika_dati[
            (laika_dati["laiks_s"] >= uv_beigas) &
            (laika_dati["laiks_s"] < cikla_beigas)
        ]

        if cikla_dati.empty:
            continue

        C_sakums = cikla_dati["videja_aptumsosanas_pakape_proc"].iloc[0]

        C_max = cikla_dati["videja_aptumsosanas_pakape_proc"].max()

        t_max = cikla_dati.loc[
            cikla_dati["videja_aptumsosanas_pakape_proc"].idxmax(),
            "laiks_min"
        ]

        # Cikla beigu vērtība, pēdējo 3 punktu vidējā vērtība atkrāsošanās posmā
        if not atkr_dati.empty:
            C_beigas = atkr_dati["videja_aptumsosanas_pakape_proc"].tail(3).mean()
            C_min_atkrasosanas_laika = atkr_dati["videja_aptumsosanas_pakape_proc"].min()
        else:
            C_beigas = np.nan
            C_min_atkrasosanas_laika = np.nan

        amplituda_no_sakuma = C_max - C_sakums

        if not np.isnan(C_beigas):
            amplituda_pec_atkrasosanas = C_max - C_beigas
        else:
            amplituda_pec_atkrasosanas = np.nan

        atlikusais_iekrasojums = C_beigas

        if C_max > 0 and not np.isnan(C_beigas):
            atjaunosanas_dala = (C_max - C_beigas) / C_max * 100
        else:
            atjaunosanas_dala = np.nan

        if uv_ieslegts_s > 0:
            krasosanas_atrums = amplituda_no_sakuma / (uv_ieslegts_s / 60)
        else:
            krasosanas_atrums = np.nan

        if uv_izslegts_s > 0 and not np.isnan(C_beigas):
            videjais_atkrasosanas_atrums = (C_beigas - C_max) / (uv_izslegts_s / 60)
        else:
            videjais_atkrasosanas_atrums = np.nan

        rezultati.append({
            "cikls": cikls + 1,
            "cikla_sakums_min": cikla_sakums / 60,
            "uv_beigas_min": uv_beigas / 60,
            "cikla_beigas_min": cikla_beigas / 60,
            "C_sakums_proc": C_sakums,
            "C_max_proc": C_max,
            "C_max_laiks_min": t_max,
            "C_beigas_proc": C_beigas,
            "C_min_atkrasosanas_laika_proc": C_min_atkrasosanas_laika,
            "amplituda_no_sakuma_proc": amplituda_no_sakuma,
            "amplituda_pec_atkrasosanas_proc": amplituda_pec_atkrasosanas,
            "atlikusais_iekrasojums_proc": atlikusais_iekrasojums,
            "atjaunosanas_dala_proc": atjaunosanas_dala,
            "krasosanas_atrums_proc_min": krasosanas_atrums,
            "videjais_atkrasosanas_atrums_proc_min": videjais_atkrasosanas_atrums
        })

    return pd.DataFrame(rezultati)


def izveidot_kopsavilkumu(ciklu_statistika):
    """
    Izveido kopējo statistiku visiem cikliem.
    """

    kopsavilkums = pd.DataFrame({
        "raditajs": [
            "Vidējā maksimālā aptumšošanās pakāpe",
            "Vidējais atlikušais iekrāsojums",
            "Vidējā cikla amplitūda pēc atkrāsošanās",
            "Vidējā atjaunošanās daļa",
            "Vidējais krāsošanās ātrums",
            "Vidējais atkrāsošanās ātrums"
        ],
        "videja_vertiba": [
            ciklu_statistika["C_max_proc"].mean(),
            ciklu_statistika["atlikusais_iekrasojums_proc"].mean(),
            ciklu_statistika["amplituda_pec_atkrasosanas_proc"].mean(),
            ciklu_statistika["atjaunosanas_dala_proc"].mean(),
            ciklu_statistika["krasosanas_atrums_proc_min"].mean(),
            ciklu_statistika["videjais_atkrasosanas_atrums_proc_min"].mean()
        ],
        "standartnovirze": [
            ciklu_statistika["C_max_proc"].std(),
            ciklu_statistika["atlikusais_iekrasojums_proc"].std(),
            ciklu_statistika["amplituda_pec_atkrasosanas_proc"].std(),
            ciklu_statistika["atjaunosanas_dala_proc"].std(),
            ciklu_statistika["krasosanas_atrums_proc_min"].std(),
            ciklu_statistika["videjais_atkrasosanas_atrums_proc_min"].std()
        ]
    })

    return kopsavilkums


dati_ar_spektriem = nolasit_visus_spektrus(DATU_MAPE)

laika_dati, aptumsosanas_spektri, sakuma_spektrs = (
    aprekinat_aptumsosanos_no_sakuma_spektra(dati_ar_spektriem)
)

ciklu_statistika = analizet_ciklus(
    laika_dati,
    REZIMS,
    CIKLU_SKAITS
)

kopsavilkums = izveidot_kopsavilkumu(ciklu_statistika)

laika_dati.to_csv(
    f"laika_dati_aptumsosanas_pakape_{REZIMS}.csv",
    index=False,
    encoding="utf-8-sig"
)

ciklu_statistika.to_csv(
    f"ciklu_statistika_{REZIMS}.csv",
    index=False,
    encoding="utf-8-sig"
)

kopsavilkums.to_csv(
    f"kopsavilkums_{REZIMS}.csv",
    index=False,
    encoding="utf-8-sig"
)

sakuma_spektrs.to_csv(
    f"sakuma_spektrs_S0_{REZIMS}.csv",
    index=False,
    encoding="utf-8-sig"
)

aptumsosanas_spektri.to_csv(
    f"aptumsosanas_spektri_lambda_{REZIMS}.csv",
    index=False,
    encoding="utf-8-sig"
)


print("Analīze pabeigta.")
print()
print("Pirmie 10 faili pēc laika:")
print(laika_dati[["fails", "merijuma_laiks", "laiks_min"]].head(10))

print()
print("Pēdējie 10 faili pēc laika:")
print(laika_dati[["fails", "merijuma_laiks", "laiks_min"]].tail(10))

print()
print("Ciklu statistika:")
print(ciklu_statistika)

print()
print("Kopsavilkums:")
print(kopsavilkums)


plt.figure(figsize=(11, 6))

plt.plot(
    laika_dati["laiks_min"],
    laika_dati["videja_aptumsosanas_pakape_proc"],
    marker="o",
    linewidth=1
)

plt.xlabel("Laiks, min")
plt.ylabel(
    f"Vidējā aptumšošanās pakāpe ({VILNA_GARUMS_MIN}-{VILNA_GARUMS_MAX} nm), %"
)
plt.title(f"Aptumšošanās dinamikas grafiks, režīms: {REZIMS}")
plt.grid(True)

# UV ieslēgšanas posmi 
uv_ieslegts_s = REZIMI[REZIMS]["uv_ieslegts_s"]
uv_izslegts_s = REZIMI[REZIMS]["uv_izslegts_s"]
cikla_ilgums_s = uv_ieslegts_s + uv_izslegts_s

for cikls in range(CIKLU_SKAITS):
    sakums_min = cikls * cikla_ilgums_s / 60
    uv_beigas_min = (cikls * cikla_ilgums_s + uv_ieslegts_s) / 60

    plt.axvspan(sakums_min, uv_beigas_min, alpha=0.15)

plt.tight_layout()
plt.savefig(f"aptumsosanas_dinamika_{REZIMS}.png", dpi=300)
plt.show()


plt.figure(figsize=(8, 5))

plt.plot(
    ciklu_statistika["cikls"],
    ciklu_statistika["C_max_proc"],
    marker="o",
    label="Maksimālā aptumšošanās"
)

plt.plot(
    ciklu_statistika["cikls"],
    ciklu_statistika["atlikusais_iekrasojums_proc"],
    marker="o",
    label="Atlikušais iekrāsojums"
)

plt.xlabel("Cikla numurs")
plt.ylabel("Aptumšošanās pakāpe, %")
plt.title(f"Ciklu salīdzinājums, režīms: {REZIMS}")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig(f"ciklu_salīdzinajums_{REZIMS}.png", dpi=300)
plt.show()