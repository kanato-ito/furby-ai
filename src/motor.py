"""モーター制御（GPIO デジタル出力, PNPトランジスタ駆動）

PNP トランジスタ駆動のため:
  LOW  = モーター ON
  HIGH = モーター OFF
"""
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False


class Motor:
    def __init__(self, pin: int) -> None:
        self.pin = pin
        if HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            GPIO.output(self.pin, GPIO.HIGH)

    def on(self) -> None:
        if HAS_GPIO:
            GPIO.output(self.pin, GPIO.LOW)

    def off(self) -> None:
        if HAS_GPIO:
            GPIO.output(self.pin, GPIO.HIGH)

    def cleanup(self) -> None:
        if HAS_GPIO:
            GPIO.output(self.pin, GPIO.HIGH)
            GPIO.cleanup()
