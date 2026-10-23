
#include <Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <string.h>
#include <stdlib.h>

// =============================================
// MOSQUISENSE: SOUND DETECTION + TIME + DATA
// Arduino Mega 2560
// =============================================

const int MIC_PIN = A0;
const int ESC_PIN = 9;

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_ADDRESS 0x3C

Adafruit_SSD1306 display(
  SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1
);

// ---------- ESC ----------
Servo esc;

const int ESC_STOP_US = 1000;
const int ESC_RUN_US = 1500;  // Nominal 50% throttle

// ---------- SOUND DETECTION ----------
const float MIN_MOSQUITO_HZ = 250.0;
const float MAX_MOSQUITO_HZ = 1000.0;

const int SAMPLE_COUNT = 512;
const int MIN_PEAK_TO_PEAK = 10;
const int HYSTERESIS = 4;
const int REQUIRED_MATCHES = 3;

uint16_t audioSamples[SAMPLE_COUNT];

// ---------- MOTOR TIMING ----------
const unsigned long ARM_TIME_MS = 5000UL;
const unsigned long MOTOR_RUN_MS = 10000UL;
const unsigned long MIC_SETTLE_MS = 800UL;

// ---------- DATA REPORTING ----------
const unsigned long REPORT_INTERVAL_MS = 300000UL;
const unsigned long OLED_REFRESH_MS = 200UL;

// ---------- MOTOR STATE ----------
bool escReady = false;
bool motorOn = false;
bool detectionArmed = true;

unsigned long startupTime = 0;
unsigned long motorStartTime = 0;
unsigned long ignoreMicUntil = 0;
unsigned long lastDisplayTime = 0;
unsigned long lastReportTime = 0;
unsigned long lastDetectionTime = 0;

unsigned long motorActivations = 0;
unsigned long detectionsInInterval = 0;

int consecutiveMatches = 0;
int consecutiveOutside = 0;

float measuredFrequency = 0.0;
int signalPeakToPeak = 0;

// ---------- CLOCK FROM COMPUTER ----------
bool clockValid = false;

int clockYear = 2026;
int clockMonth = 10;
int clockDay = 23;

int clockHour = 10;
int clockMinute = 0;
int clockSecond = 0;

unsigned long lastClockTick = 0;

// ---------- SERIAL INPUT ----------
char serialBuffer[80];
byte serialIndex = 0;


// =============================================
// CLOCK FUNCTIONS
// =============================================

bool isLeapYear(int year) {
  return (year % 400 == 0) ||
         (year % 4 == 0 && year % 100 != 0);
}

int daysInMonth(int month, int year) {

  if (month == 2) {
    return isLeapYear(year) ? 29 : 28;
  }

  if (month == 4 || month == 6 ||
      month == 9 || month == 11) {
    return 30;
  }

  return 31;
}

void advanceOneSecond() {

  clockSecond++;

  if (clockSecond >= 60) {
    clockSecond = 0;
    clockMinute++;
  }

  if (clockMinute >= 60) {
    clockMinute = 0;
    clockHour++;
  }

  if (clockHour >= 24) {
    clockHour = 0;
    clockDay++;
  }

  if (clockDay > daysInMonth(clockMonth, clockYear)) {
    clockDay = 1;
    clockMonth++;
  }

  if (clockMonth > 12) {
    clockMonth = 1;
    clockYear++;
  }
}

void updateClock() {

  if (!clockValid) {
    return;
  }

  unsigned long now = millis();

  while (now - lastClockTick >= 1000UL) {
    lastClockTick += 1000UL;
    advanceOneSecond();
  }
}


// =============================================
// RECEIVE TIME FROM PYTHON
//
// Python sends:
// TIME,2026,10,23,14,35,00
// =============================================

void processSerialLine(char *line) {

  if (strncmp(line, "TIME,", 5) != 0) {
    return;
  }

  char *field = strtok(line, ",");
  int values[6];

  for (int i = 0; i < 6; i++) {

    field = strtok(NULL, ",");

    if (field == NULL || field[0] == '\0') {
      return;
    }

    // Accept digits only
    for (int j = 0; field[j] != '\0'; j++) {
      if (field[j] < '0' || field[j] > '9') {
        return;
      }
    }

    values[i] = atoi(field);
  }

  if (strtok(NULL, ",") != NULL) {
    return;
  }

  int y = values[0];
  int mo = values[1];
  int d = values[2];
  int h = values[3];
  int mi = values[4];
  int s = values[5];

  if (y < 2020 || y > 2099 ||
      mo < 1 || mo > 12 ||
      d < 1 || d > daysInMonth(mo, y) ||
      h < 0 || h > 23 ||
      mi < 0 || mi > 59 ||
      s < 0 || s > 59) {
    return;
  }

  clockYear = y;
  clockMonth = mo;
  clockDay = d;
  clockHour = h;
  clockMinute = mi;
  clockSecond = s;

  clockValid = true;
  lastClockTick = millis();
}

void readSerialInput() {

  while (Serial.available() > 0) {

    char incoming = Serial.read();

    if (incoming == '\r') {
      continue;
    }

    if (incoming == '\n') {

      serialBuffer[serialIndex] = '\0';

      if (serialIndex > 0) {
        processSerialLine(serialBuffer);
      }

      serialIndex = 0;

    } else if (serialIndex < sizeof(serialBuffer) - 1) {

      serialBuffer[serialIndex++] = incoming;

    } else {

      // Discard oversized line
      serialIndex = 0;
    }
  }
}


// =============================================
// AUDIO FREQUENCY MEASUREMENT
// =============================================

bool measureFrequency(
  float &frequency,
  int &peakToPeak
) {

  uint32_t sum = 0;

  int minimumValue = 1023;
  int maximumValue = 0;

  unsigned long captureStart = micros();

  for (int i = 0; i < SAMPLE_COUNT; i++) {

    int sample = analogRead(MIC_PIN);

    audioSamples[i] = sample;
    sum += sample;

    if (sample < minimumValue) {
      minimumValue = sample;
    }

    if (sample > maximumValue) {
      maximumValue = sample;
    }
  }

  unsigned long captureDuration =
    micros() - captureStart;

  peakToPeak = maximumValue - minimumValue;

  if (peakToPeak < MIN_PEAK_TO_PEAK ||
      captureDuration == 0) {

    frequency = 0;
    return false;
  }

  int baseline = sum / SAMPLE_COUNT;

  int lowerThreshold = baseline - HYSTERESIS;
  int upperThreshold = baseline + HYSTERESIS;

  bool signalWentLow = false;
  unsigned int risingCrossings = 0;

  for (int i = 0; i < SAMPLE_COUNT; i++) {

    int sample = audioSamples[i];

    if (sample < lowerThreshold) {

      signalWentLow = true;

    } else if (
      signalWentLow &&
      sample > upperThreshold
    ) {

      risingCrossings++;
      signalWentLow = false;
    }
  }

  if (risingCrossings < 4) {
    frequency = 0;
    return false;
  }

  frequency =
    (float)risingCrossings *
    1000000.0 /
    (float)captureDuration;

  return true;
}


// =============================================
// MOTOR CONTROL
// =============================================

void startMotor() {

  if (!escReady || motorOn) {
    return;
  }

  motorOn = true;
  motorStartTime = millis();
  lastDetectionTime = motorStartTime;

  motorActivations++;
  detectionsInInterval++;

  esc.writeMicroseconds(ESC_RUN_US);
}

void stopMotor() {

  esc.writeMicroseconds(ESC_STOP_US);

  motorOn = false;
  ignoreMicUntil = millis() + MIC_SETTLE_MS;

  consecutiveMatches = 0;
  consecutiveOutside = 0;
}


// =============================================
// DETECTION PROCESSING
// =============================================

void processAudio() {

  float frequency = 0;
  int peakToPeak = 0;

  bool measurable =
    measureFrequency(frequency, peakToPeak);

  measuredFrequency = measurable ? frequency : 0;
  signalPeakToPeak = measurable ? peakToPeak : 0;

  bool inRange =
    measurable &&
    frequency >= MIN_MOSQUITO_HZ &&
    frequency <= MAX_MOSQUITO_HZ;

  if (inRange) {

    consecutiveOutside = 0;

    if (consecutiveMatches < REQUIRED_MATCHES) {
      consecutiveMatches++;
    }

    if (detectionArmed &&
        consecutiveMatches >= REQUIRED_MATCHES) {

      detectionArmed = false;
      startMotor();
    }

  } else {

    consecutiveMatches = 0;

    if (consecutiveOutside < 3) {
      consecutiveOutside++;
    }

    if (consecutiveOutside >= 3) {
      detectionArmed = true;
    }
  }
}


// =============================================
// SEND DATA EVERY FIVE MINUTES
//
// Packet format:
// DATA,date,time,interval_events,frequency,
//      peak_to_peak,total_motor_activations
//
// Example:
// DATA,2026-10-23,14:35:00,3,463.0,23,4
// =============================================

void sendPeriodicData() {

  unsigned long now = millis();

  if (now - lastReportTime < REPORT_INTERVAL_MS) {
    return;
  }

  lastReportTime = now;

  Serial.print("DATA,");

  if (clockValid) {

    Serial.print(clockYear);
    Serial.print("-");

    if (clockMonth < 10) Serial.print("0");
    Serial.print(clockMonth);
    Serial.print("-");

    if (clockDay < 10) Serial.print("0");
    Serial.print(clockDay);

    Serial.print(",");

    if (clockHour < 10) Serial.print("0");
    Serial.print(clockHour);
    Serial.print(":");

    if (clockMinute < 10) Serial.print("0");
    Serial.print(clockMinute);
    Serial.print(":");

    if (clockSecond < 10) Serial.print("0");
    Serial.print(clockSecond);

  } else {

    Serial.print("UNSYNCED,UNSYNCED");
  }

  Serial.print(",");
  Serial.print(detectionsInInterval);

  Serial.print(",");
  Serial.print(measuredFrequency, 1);

  Serial.print(",");
  Serial.print(signalPeakToPeak);

  Serial.print(",");
  Serial.println(motorActivations);

  // Start a new reporting interval
  detectionsInInterval = 0;
}


// =============================================
// OLED DISPLAY
// =============================================

void updateOLED() {

  unsigned long now = millis();

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  // Line 1
  display.setCursor(0, 0);
  display.println("MOSQUISENSE");

  // Line 2: current date and time
  display.setCursor(0, 8);

  if (clockValid) {

    if (clockDay < 10) display.print("0");
    display.print(clockDay);
    display.print("/");

    if (clockMonth < 10) display.print("0");
    display.print(clockMonth);
    display.print("/");

    display.print(clockYear % 100);
    display.print(" ");

    if (clockHour < 10) display.print("0");
    display.print(clockHour);
    display.print(":");

    if (clockMinute < 10) display.print("0");
    display.println(clockMinute);

  } else {

    display.println("Time: WAITING FOR PC");
  }

  // Line 3: detection status
  display.setCursor(0, 16);

  if (!escReady) {
    display.println("Status: ESC ARMING");
  } else if (motorOn) {
    display.println("Status: SOUND DETECTED");
  } else if (now - lastDetectionTime < 3000UL) {
    display.println("Status: DETECTED!");
  } else {
    display.println("Status: LISTENING");
  }

  // Line 4: frequency
  display.setCursor(0, 24);
  display.print("Freq: ");

  if (measuredFrequency > 0) {
    display.print(measuredFrequency, 0);
    display.println(" Hz");
  } else {
    display.println("--- Hz");
  }

  // Line 5: motor status
  display.setCursor(0, 32);
  display.print("Motor: ");

  if (!escReady || !motorOn) {
    display.println("OFF");
  } else {
    display.println("ON 50%");
  }

  // Line 6: detections in current 5-minute interval
  display.setCursor(0, 40);
  display.print("5m events: ");
  display.println(detectionsInInterval);

  // Line 7: cumulative activations
  display.setCursor(0, 48);
  display.print("Starts: ");
  display.println(motorActivations);

  // Line 8: signal and warning
  display.setCursor(0, 56);
  display.print("p-p:");
  display.print(signalPeakToPeak);
  display.print(" BE CAREFUL!");

  display.display();
}


// =============================================
// SETUP
// =============================================

void setup() {

  Serial.begin(9600);

  pinMode(MIC_PIN, INPUT);

  esc.attach(ESC_PIN, 1000, 2000);
  esc.writeMicroseconds(ESC_STOP_US);

  Wire.begin();

  if (!display.begin(
    SSD1306_SWITCHCAPVCC,
    OLED_ADDRESS
  )) {

    while (true) {
      esc.writeMicroseconds(ESC_STOP_US);
      delay(100);
    }
  }

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("MOSQUISENSE");
  display.println("Waiting for setup...");
  display.display();

  startupTime = millis();
  lastReportTime = startupTime;
}


// =============================================
// MAIN LOOP
// =============================================

void loop() {

  readSerialInput();
  updateClock();

  unsigned long now = millis();

  // ESC startup
  if (!escReady) {

    esc.writeMicroseconds(ESC_STOP_US);

    if (now - startupTime >= ARM_TIME_MS) {

      escReady = true;
      ignoreMicUntil = millis() + MIC_SETTLE_MS;
    }
  }

  // Stop motor after 10 seconds
  if (motorOn &&
      now - motorStartTime >= MOTOR_RUN_MS) {

    stopMotor();
  }

  // Listen only while motor is OFF
  if (escReady &&
      !motorOn &&
      (long)(now - ignoreMicUntil) >= 0) {

    processAudio();
  }

  // Send data packet every 5 minutes
  sendPeriodicData();

  // Refresh display
  now = millis();

  if (now - lastDisplayTime >= OLED_REFRESH_MS) {

    lastDisplayTime = now;
    updateOLED();
  }
}
