"""モーター制御（GPIO デジタル出力, PNPトランジスタ駆動）

PNP トランジスタ駆動のため:
  LOW  = モーター ON
  HIGH = モーター OFF
gpiozero の active_high=False でこの反転を表す（on() で LOW を出力）。
"""
import asyncio

try:
    from gpiozero import DigitalOutputDevice
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False


class Motor:
    def __init__(self, pin: int, pulse_on_ms: int = 150, pulse_off_ms: int = 120) -> None:
        self.pin = pin
        self.pulse_on_s = pulse_on_ms / 1000
        self.pulse_off_s = pulse_off_ms / 1000
        self.device = None
        if HAS_GPIO:
            try:
                self.device = DigitalOutputDevice(pin, active_high=False, initial_value=False)
            except Exception as e:  # Pi 以外（ピンファクトリなし）
                print(f"[Motor] GPIO 無効: {e}")

    def on(self) -> None:
        if self.device:
            self.device.on()

    def off(self) -> None:
        if self.device:
            self.device.off()

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
        if self.device:
            self.device.off()
            self.device.close()
