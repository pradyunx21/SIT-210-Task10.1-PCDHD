#include <SPI.h>
#include <MFRC522.h>
#include <Servo.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo servo;

int servoPos = 0;
#define sensorPin1 A2  // Entry IR sensor
#define sensorPin2 A3  // Exit IR sensor
#define buzzerPin 3

// Define frequencies for different tones
#define TONE_SUCCESS 2000  // Higher frequency for success
#define TONE_ERROR 1000    // Lower frequency for error

int senVal1 = 0;
int senVal2 = 0;

#define RST_PIN 8
#define SS_PIN 10

int card1Balance = 4153;
int card2Balance = 1890;

MFRC522 mfrc522(SS_PIN, RST_PIN);
int state = 0;  // 0 = Waiting, 1 = Authorized and Opened

void setup() {
  lcd.begin();
  lcd.backlight();
  Serial.begin(9600);

  servo.attach(9);  // Attach once in setup
  servo.write(30);  // Start with the barrier down position

  pinMode(sensorPin1, INPUT);
  pinMode(sensorPin2, INPUT);
  pinMode(buzzerPin, OUTPUT);

  SPI.begin();
  mfrc522.PCD_Init();

  lcd.setCursor(0, 0);
  lcd.print(" Automatic Toll");
  lcd.setCursor(0, 1);
  lcd.print("Collection System");
  delay(3000);
  lcd.clear();
}

void loop() {
  lcd.setCursor(0, 0);
  lcd.print("    Welcome");

  sensorRead();
  rfid();

  // Detect vehicle at entry using sensor 1 and check if RFID authorization is done
  if (senVal1 == 0 && state == 1) {
    servoDown();  // Lower barrier after detection and authorization
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Vehicle Detected");
    delay(1000);
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Authorized Access");
    delay(2000);
    lcd.clear();
  }

  // Detect vehicle has passed using sensor 2 and close the barrier if it was opened
  if (senVal2 == 0 && state == 1) {
    servoUp();  // Raise barrier to close after vehicle has exited
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Have A Safe");
    lcd.setCursor(0, 1);
    lcd.print("Journey");
    delay(1000);
    lcd.clear();
    state = 0;  // Reset state after allowing vehicle to pass and close barrier
  }
}

void sendData(const char* event, int cardId = 0, int amount = 0, int balance = 0) {
  // Format: event,cardId,amount,balance
  Serial.print(event);
  Serial.print(",");
  Serial.print(cardId);
  Serial.print(",");
  Serial.print(amount);
  Serial.print(",");
  Serial.println(balance);
}

void servoDown() {
  for (servoPos = 30; servoPos <= 120; servoPos += 1) {
    servo.write(servoPos);
    delay(5);
  }
}

void servoUp() {
  for (servoPos = 120; servoPos >= 30; servoPos -= 1) {
    servo.write(servoPos);
    delay(5);
  }
  delay(1000);
  sendData("CAPTURE");
}

void sensorRead() {
  senVal1 = digitalRead(sensorPin1);
  senVal2 = digitalRead(sensorPin2);
  delay(50);  // Debounce delay for stable readings
}

void rfid() {
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return;  // No card detected, exit function
  }

  String content = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    content.concat(String(mfrc522.uid.uidByte[i] < 0x10 ? " 0" : " "));
    content.concat(String(mfrc522.uid.uidByte[i], HEX));
  }
  content.toUpperCase();

  if (content.substring(1) == "53 9C AA F5") {
    processCard(card1Balance);
  }
  else if (content.substring(1) == "20 54 E8 22") {
    processCard(card2Balance);
  }
  else {
    denyAccess();
  }
}

void processCard(int &cardBalance) {
  if (cardBalance >= 500) {
    lcdPrint();
    int previousBalance = cardBalance;
    cardBalance -= 100;
    // Send transaction data
    sendData("TRANSACTION", mfrc522.uid.uidByte[0], 100, cardBalance);
    lcd.setCursor(9, 1);
    lcd.print(cardBalance);
    delay(2000);
    lcd.clear();
    state = 1;
  } else {
    displayInsufficientBalance(cardBalance);
    sendData("INSUFFICIENT", mfrc522.uid.uidByte[0], 0, cardBalance);
  }
}

void soundBuzzer(bool isSuccess) {
  if (isSuccess) {
    // Success pattern: Three loud beeps with ascending tones
    for (int i = 0; i < 3; i++) {
      tone(buzzerPin, TONE_SUCCESS + (i * 500), 150);  // Increasing frequency
      delay(200);
      noTone(buzzerPin);
      delay(100);
    }
  } else {
    // Error pattern: Two loud descending tones
    tone(buzzerPin, TONE_ERROR + 500, 300);  // Start with higher tone
    delay(350);
    noTone(buzzerPin);
    delay(100);
    tone(buzzerPin, TONE_ERROR, 500);  // End with lower tone
    delay(550);
    noTone(buzzerPin);
  }
}

void lcdPrint() {
  soundBuzzer(true);  // Success sound
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("  Successfully");
  lcd.setCursor(0, 1);
  lcd.print(" paid your bill");
  delay(1500);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Your Remaining");
  lcd.setCursor(0, 1);
  lcd.print("balance: ");
}

void displayInsufficientBalance(int cardBalance) {
  soundBuzzer(false);  // Error sound
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("  Your balance");
  lcd.setCursor(0, 1);
  lcd.print(" is insufficient");
  delay(1500);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Your Remaining");
  lcd.setCursor(0, 1);
  lcd.print("balance: ");
  lcd.print(cardBalance);
  delay(2000);
  lcd.clear();
  state = 0;
}

void denyAccess() {
  soundBuzzer(false);  // Error sound
  lcd.setCursor(0, 0);
  lcd.print("Unknown Vehicle");
  lcd.setCursor(0, 1);
  lcd.print("Access denied");
  delay(1500);
  lcd.clear();
  state = 0;  // Ensure state is reset if access is denied
}