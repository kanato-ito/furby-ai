"""
テスト07: モーター（GPIO）確認
実行方法: python3 src/test_07_motor.py
確認内容: GPIO 17 を ON/OFF してモーターが動作するか確認する
注意: Raspberry Pi 上でのみ動作します
トランジスタ: S8550（PNP） — LOW=ON / HIGH=OFF
配線: 3V3(1) → E, B → [1kΩ] → GPIO17(11), C → モーター(+), モーター(-) → GND(6)
"""
import sys
import time

MOTOR_PIN = 17
ON_SEC = 2.0
OFF_SEC = 1.0
REPEAT = 3

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("NG: RPi.GPIO が見つかりません。Raspberry Pi 上で実行してください。")
    sys.exit(1)


def main():
    print("=== テスト07: モーター（GPIO）確認 ===\n")
    print(f"GPIO ピン : {MOTOR_PIN} (BCM番号 / 物理ピン11)")
    print(f"ON 時間   : {ON_SEC}秒")
    print(f"OFF 時間  : {OFF_SEC}秒")
    print(f"繰り返し  : {REPEAT}回\n")

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(MOTOR_PIN, GPIO.OUT)
    GPIO.output(MOTOR_PIN, GPIO.HIGH)  # PNP: HIGH = OFF（初期状態）

    try:
        for i in range(1, REPEAT + 1):
            print(f"[{i}/{REPEAT}] モーター ON  → GPIO {MOTOR_PIN} = LOW")
            GPIO.output(MOTOR_PIN, GPIO.LOW)   # PNP: LOW = ON
            time.sleep(ON_SEC)

            print(f"[{i}/{REPEAT}] モーター OFF → GPIO {MOTOR_PIN} = HIGH")
            GPIO.output(MOTOR_PIN, GPIO.HIGH)  # PNP: HIGH = OFF
            time.sleep(OFF_SEC)
            print()
    finally:
        GPIO.output(MOTOR_PIN, GPIO.HIGH)  # PNP: 終了時は必ず OFF
        GPIO.cleanup()

    print("✓ テスト07 完了")
    print("\nモーターが動かない場合:")
    print("  ・S8550 の向き（平面側を手前）: 左=E, 中=B, 右=C")
    print("  ・3V3(1) → E, B → [1kΩ] → GPIO17(11), C → モーター(+), モーター(-) → GND(6)")


if __name__ == '__main__':
    main()
