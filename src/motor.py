"""モーター制御（GPIO デジタル出力, PNPトランジスタ駆動）

PNP トランジスタ駆動のため:
  LOW  = モーター ON
  HIGH = モーター OFF
"""
import asyncio

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False


class Motor:
    def __init__(self, pin: int, pulse_on_ms: int = 150, pulse_off_ms: int = 120) -> None:
        self.pin = pin
        self.pulse_on_s = pulse_on_ms / 1000
        self.pulse_off_s = pulse_off_ms / 1000
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

    async def pulse(self) -> None:
        """キャンセルされるまでパクパク動く（口の開閉を模擬）"""
        try:
            while True:
                self.on()
                await asyncio.sleep(self.pulse_on_s)
                self.off()
                await asyncio.sleep(self.pulse_off_s)
        except asyncio.CancelledError:
            self.off()
            raise

    def cleanup(self) -> None:
        if HAS_GPIO:
            GPIO.output(self.pin, GPIO.HIGH)
            GPIO.cleanup()
