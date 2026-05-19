"""
テスト07: モーター（GPIO）確認
実行方法: python3 src/test_07_motor.py
確認内容: GPIO 17 を ON/OFF してモーターが動作するか確認する
注意: Raspberry Pi 上でのみ動作します
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
    GPIO.output(MOTOR_PIN, GPIO.LOW)

    try:
        for i in range(1, REPEAT + 1):
            print(f"[{i}/{REPEAT}] モーター ON  → GPIO {MOTOR_PIN} = HIGH")
            GPIO.output(MOTOR_PIN, GPIO.HIGH)
            time.sleep(ON_SEC)

            print(f"[{i}/{REPEAT}] モーター OFF → GPIO {MOTOR_PIN} = LOW")
            GPIO.output(MOTOR_PIN, GPIO.LOW)
            time.sleep(OFF_SEC)
            print()
    finally:
        GPIO.output(MOTOR_PIN, GPIO.LOW)
        GPIO.cleanup()

    print("✓ テスト07 完了")
    print("\nモーターが動かない場合:")
    print("  ・配線（GPIO 17 → モーター → GND）を確認")
    print("  ・テスターでGPIO 17 の電圧（HIGH時 3.3V）を確認")
    print("  ・モーター消費電流が 16mA 超の場合はトランジスタ回路に変更")


if __name__ == '__main__':
    main()
