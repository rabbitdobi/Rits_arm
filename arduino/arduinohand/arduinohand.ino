// arduinohand.ino
// PCから "親指,人差し指,中指,薬指,小指[,手首]" を受け取って、ハンドを動かす
// 指:   0 = 握る, 180 = 開く
// 手首: 0〜180（6つ目は省略可。省略したら手首は今の位置のまま）
// 受け取った 0〜180 は、それぞれの安全な範囲（MIN〜MAX）に変換される

#include <Servo.h>

// ===== 設定 =====
const long BAUD = 115200;
const unsigned long TIMEOUT_MS = 1000;  // これ以上データが来なければ「途切れた」と判断
const bool ECHO = true;                 // 受け取った角度をシリアルモニタに表示するか

const uint8_t FINGER_PINS[5] = {7, 6, 5, 4, 3};  // 親指, 人差し指, 中指, 薬指, 小指
const uint8_t WRIST_PIN = 2;

// 指ごとの動ける範囲（実際に測った値）
const int FINGER_MIN[5] = {30, 30, 30, 30, 30};       // 握る側の限界
const int FINGER_MAX[5] = {140, 140, 140, 140, 140};  // 開く側の限界

// 手首の動ける範囲（まだ仮の値。測ったら書き換える）
const int WRIST_MIN = 45;
const int WRIST_MAX = 135;

// ===== ここから下は基本さわらなくてOK =====
Servo fingers[5];
Servo wrist;

char buf[48];
uint8_t len = 0;
unsigned long lastReceived = 0;
bool timedOut = false;

// 0〜180 の入力を、指定した範囲に変換
int toRange(int input, int minA, int maxA) {
  input = constrain(input, 0, 180);
  return map(input, 0, 180, minA, maxA);
}

// 親指(0)だけ向きが逆なので反転して書き込む
void writeFinger(int i, int angle) {
  fingers[i].write(i == 0 ? 180 - angle : angle);
}

// 手首も向きが逆
void writeWrist(int angle) {
  wrist.write(180 - angle);
}

// 1行分のデータを読んで、ハンドを動かす
void handleLine(char* line) {
  int a[6];
  int n = sscanf(line, "%d,%d,%d,%d,%d,%d", &a[0], &a[1], &a[2], &a[3], &a[4], &a[5]);
  if (n != 5 && n != 6) {
    if (ECHO) Serial.println("ERR bad format");  // 形がおかしいデータは無視
    return;
  }

  int angles[5];
  for (int i = 0; i < 5; i++) {
    angles[i] = toRange(a[i], FINGER_MIN[i], FINGER_MAX[i]);
    writeFinger(i, angles[i]);
  }

  int wristAngle = -1;
  if (n == 6) {
    wristAngle = toRange(a[5], WRIST_MIN, WRIST_MAX);
    writeWrist(wristAngle);
  }

  lastReceived = millis();
  timedOut = false;

  if (ECHO) {
    Serial.print("OK servo=");
    for (int i = 0; i < 5; i++) {
      Serial.print(angles[i]);
      Serial.print(",");
    }
    if (wristAngle >= 0) {
      Serial.print(" wrist=");
      Serial.println(wristAngle);
    } else {
      Serial.println(" wrist=(unchanged)");
    }
  }
}

void setup() {
  Serial.begin(BAUD);

  // 最初は指を全部開いて、手首は真ん中にしてから接続（急に動かないように）
  for (int i = 0; i < 5; i++) {
    writeFinger(i, FINGER_MAX[i]);
    fingers[i].attach(FINGER_PINS[i]);
  }
  writeWrist(toRange(90, WRIST_MIN, WRIST_MAX));
  wrist.attach(WRIST_PIN);

  lastReceived = millis();
  Serial.println("READY");
}

void loop() {
  // 届いた文字を1つずつためて、改行が来たら1行として処理
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      buf[len] = '\0';
      handleLine(buf);
      len = 0;
    } else if (c != '\r') {
      if (len < sizeof(buf) - 1) {
        buf[len++] = c;
      } else {
        len = 0;  // 長すぎるデータは捨てる
      }
    }
  }

  // データが途切れたら、その場で止まる（新しい指示を出さないだけ）
  if (!timedOut && millis() - lastReceived > TIMEOUT_MS) {
    timedOut = true;
    if (ECHO) Serial.println("TIMEOUT (holding position)");
  }
}