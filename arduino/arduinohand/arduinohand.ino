// hand_receiver.ino
// PCから "親指,人差し指,中指,薬指,小指" を受け取って、ハンドの指を動かす
// 例: "180,90,90,90,180"   180 = 開く, 0 = 握る
// 受け取った 0〜180 は、各指の動ける範囲（FINGER_MIN〜FINGER_MAX）に変換される

#include <Servo.h>

// ===== 設定 =====
const long BAUD = 115200;
const unsigned long TIMEOUT_MS = 1000;  // これ以上データが来なければ「途切れた」と判断
const bool ECHO = true;                 // 受け取った角度をシリアルモニタに表示するか

const uint8_t FINGER_PINS[5] = {7, 6, 5, 4, 3};  // 親指, 人差し指, 中指, 薬指, 小指
const uint8_t WRIST_PIN = 2;
const int WRIST_ANGLE = 90;                       // 手首は真ん中で固定

// 指ごとの動ける範囲（実際に測った値）
const int FINGER_MIN[5] = {30, 30, 30, 30, 30};       // 握る側の限界
const int FINGER_MAX[5] = {140, 140, 140, 140, 140};  // 開く側の限界

// ===== ここから下は基本さわらなくてOK =====
Servo fingers[5];
Servo wrist;

char buf[40];
uint8_t len = 0;
unsigned long lastReceived = 0;
bool timedOut = false;

// 0〜180 の入力を、その指の動ける範囲に変換
int toServoAngle(int i, int input) {
  input = constrain(input, 0, 180);
  return map(input, 0, 180, FINGER_MIN[i], FINGER_MAX[i]);
}

// 親指(0)だけ向きが逆なので反転して書き込む
void writeFinger(int i, int angle) {
  fingers[i].write(i == 0 ? 180 - angle : angle);
}

// 1行分のデータを読んで、指を動かす
void handleLine(char* line) {
  int a[5];
  if (sscanf(line, "%d,%d,%d,%d,%d", &a[0], &a[1], &a[2], &a[3], &a[4]) != 5) {
    if (ECHO) Serial.println("ERR bad format");  // 形がおかしいデータは無視
    return;
  }

  int angles[5];
  for (int i = 0; i < 5; i++) {
    angles[i] = toServoAngle(i, a[i]);
    writeFinger(i, angles[i]);
  }
  lastReceived = millis();
  timedOut = false;

  if (ECHO) {
    Serial.print("OK servo=");
    for (int i = 0; i < 5; i++) {
      Serial.print(angles[i]);
      Serial.print(i < 4 ? "," : "\n");
    }
  }
}

void setup() {
  Serial.begin(BAUD);

  // 最初は全部開いた状態にしてから接続（急に動かないように）
  for (int i = 0; i < 5; i++) {
    writeFinger(i, FINGER_MAX[i]);
    fingers[i].attach(FINGER_PINS[i]);
  }
  wrist.write(180 - WRIST_ANGLE);  // 手首も向きが逆
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