#!/usr/bin/python3

import enum
import serial
import glob

class VEDirectException(Exception):
    pass

class InvalidChecksumException(VEDirectException):
    pass

class MPPTState(enum.Enum):
    Off = 0
    Limited = 1
    Active = 2


def mA(val: str) -> float:
    return float(val) / 1000

def mV(val: str) -> float:
    return float(val) / 1000


def auto_detect_device():
    """Automatically detects a USB serial device in /dev/ for both Linux and macOS."""
    # Device patterns to search for
    patterns = [
        '/dev/ttyUSB*',        # Linux USB serial devices
        '/dev/tty.usbserial*', # macOS USB serial devices (tty only)
    ]
    usb_devices = []
    for pattern in patterns:
        devices = glob.glob(pattern)
        if devices:
            usb_devices.extend(devices)
    if usb_devices:
        return usb_devices[0]  # Return the first USB device found
    else:
        raise VEDirectException("No USB serial device found in /dev matching known patterns.")


class VEDirect:
    def __init__(self, device: str = None, speed: int = 19200):
        self.device = device or auto_detect_device()  # Use auto-detected device if none provided
        self.speed = speed
        self._data = {}

        self.refresh()

    def refresh(self):
        frames = self._get_data()
        self.parse_pdu(frames)

    def parse_pdu(self, frames):
        for frame in frames:
            if frame.startswith(b'Checksum'):
                # This entry is useless
                continue
            key_value = frame.strip().decode('utf-8')
            if '\t' in key_value:
                key, value = key_value.split('\t')
                self._data[key] = value

    def _get_data(self) -> list:
        """Returns a PDU array, one entry per line."""
        data = []
        with serial.Serial(self.device, self.speed, timeout=4) as s:
            # Wait for start of frame
            while True:
                frame = s.readline()
                if frame.startswith(b'PID'):
                    data.append(frame)
                    break

            # Read frames until the next 'PID' or until timeout
            while True:
                frame = s.readline()
                if frame.startswith(b'PID') or not frame:
                    break
                data.append(frame)

        # The checksum is for the whole DTU
        if not VEDirect.check_frame_checksum(data):
            raise InvalidChecksumException()

        return data

    @staticmethod
    def check_frame_checksum(frames: list):
        """Checks the PDU for validity.
        The checksum generates a char so that the sum
        of all characters equals 0 mod 256."""
        chksum = 0
        for frame in frames:
            for char in frame:
                chksum = (chksum + char) % 256
        return chksum == 0

    @property
    def battery_volts(self) -> float:
        """Returns the battery voltage in Volts."""
        return mV(self._data.get('V', '0'))

    @property
    def battery_amps(self) -> float:
        """Returns the battery charging current in Amps."""
        return mA(self._data.get('I', '0'))

    @property
    def solar_volts(self) -> float:
        """Returns the solar array voltage in Volts."""
        return mV(self._data.get('VPV', '0'))

    @property
    def solar_power(self) -> float:
        """Returns the solar array power in Watts."""
        return float(self._data.get('PPV', '0'))

    @property
    def device_serial(self) -> str:
        """Returns the device serial number."""
        return self._data.get('SER#', 'Unknown')

    @property
    def device_MPPT_state(self) -> MPPTState:
        """Returns the MPPT state."""
        return MPPTState(int(self._data.get('MPPT', '0')))


if __name__ == '__main__':
    try:
        v = VEDirect()
        print(f'Battery Voltage: {v.battery_volts} V')
        print(f'Battery Current: {v.battery_amps} A')
        print(f'Solar Voltage: {v.solar_volts} V')
        print(f'Solar Power: {v.solar_power} W')
        print(f'Device Serial: {v.device_serial}')
        print(f'MPPT State: {v.device_MPPT_state.name}')
    except VEDirectException as e:
        print(f"Error: {e}")

