// Pin for MOSFET gate
const int UV_PIN = 9;

// Number of stages
const int STAGES = 3;

// UV ON times in milliseconds
unsigned long uvOnTime[STAGES] = {
  30000UL,    // 30 seconds
  60000UL,    // 1 minute
  180000UL    // 3 minutes
};

// UV OFF / bleaching times in milliseconds
unsigned long uvOffTime[STAGES] = {
  300000UL,   // 5 minutes
  600000UL,   // 10 minutes
  1500000UL    // 25 minutes
};

// Number of cycles for each stage
int cyclesPerStage[STAGES] = {
  20,
  20,
  20
};

int currentStage = 0;
int currentCycle = 0;

bool uvIsOn = false;
bool experimentFinished = false;

unsigned long previousTime = 0;

void setup() {
  pinMode(UV_PIN, OUTPUT);
  digitalWrite(UV_PIN, LOW);

  Serial.begin(9600);
  delay(1000);

  Serial.println("Experiment started");
  Serial.println("Stage 1: 30 s UV ON / 5 min UV OFF");

  // Start first UV ON period
  uvIsOn = true;
  digitalWrite(UV_PIN, HIGH);
  previousTime = millis();

  Serial.println("UV ON");
}

void loop() {
  if (experimentFinished) {
    digitalWrite(UV_PIN, LOW);
    return;
  }

  unsigned long currentTime = millis();

  if (uvIsOn) {
    // UV irradiation period
    if (currentTime - previousTime >= uvOnTime[currentStage]) {
      uvIsOn = false;
      digitalWrite(UV_PIN, LOW);
      previousTime = currentTime;

      Serial.print("UV OFF, Stage ");
      Serial.print(currentStage + 1);
      Serial.print(", Cycle ");
      Serial.println(currentCycle + 1);
    }
  } 
  else {
    // Bleaching period
    if (currentTime - previousTime >= uvOffTime[currentStage]) {
      currentCycle++;

      // Check if current stage is finished
      if (currentCycle >= cyclesPerStage[currentStage]) {
        currentStage++;
        currentCycle = 0;

        // Check if all stages are finished
        if (currentStage >= STAGES) {
          experimentFinished = true;
          digitalWrite(UV_PIN, LOW);
          Serial.println("Experiment finished");
          return;
        }

        Serial.print("Next stage: ");
        Serial.println(currentStage + 1);

        if (currentStage == 1) {
          Serial.println("Stage 2: 1 min UV ON / 10 min UV OFF");
        }

        if (currentStage == 2) {
          Serial.println("Stage 3: 3 min UV ON / 25 min UV OFF");
        }
      }

      // Start next UV ON period
      uvIsOn = true;
      digitalWrite(UV_PIN, HIGH);
      previousTime = currentTime;

      Serial.print("UV ON, Stage ");
      Serial.print(currentStage + 1);
      Serial.print(", Cycle ");
      Serial.println(currentCycle + 1);
    }
  }
}
