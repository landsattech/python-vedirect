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
        '/dev/tty.usbmodem*',  # macOS USB modem devices (tty only)
    ]
    usb_devices = []
    for pattern in patterns:
        devices = glob.glob(pattern)
        if devices:
            usb_devices.extend(devices)
    if usb_devices:
        # Optionally, you can print the list of found devices
        # print("Found USB devices:", usb_devices)
        return usb_devices[0]  # Return the first USB device found
    else:
        raise VEDirectException("No USB serial device found in /dev matching known patterns.")

class VEDirect:
    OFF_REASON_CODES = {
        0x00000001: 'No input power',
        0x00000002: 'Switched off (power switch)',
        0x00000004: 'Switched off (device mode register)',
        0x00000008: 'Remote input',
        0x00000010: 'Protection active',
        0x00000020: 'Paygo active',
        0x00000040: 'Boost mode',
        0x00000080: 'Extended bulk active',
        # Add more codes as needed
    }

    ERROR_CODES = {
        0: 'No error',
        2: 'Battery voltage too high',
        17: 'Charger temperature too high',
        18: 'Charger over current',
        19: 'Charger current reversed',
        20: 'Bulk time limit exceeded',
        21: 'Current sensor issue',
        22: 'Charger temperature sensor faulty',
        26: 'Terminals overheated',
        33: 'Input voltage too high (solar panel voltage)',
        34: 'Input current too high (solar panel current)',
        38: 'Input shutdown due to battery voltage',
        116: 'Factory calibration data lost',
        117: 'Invalid/incompatible firmware',
        119: 'User settings invalid',
        # Add more codes as needed
    }

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
            key_value = frame.strip().decode('utf-8', errors='ignore')
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

    # Existing properties
    @property
    def battery_volts(self) -> float:
        """Returns the battery voltage in Volts."""
        return mV(self._data.get('V', '0'))

    @property
    def battery_amps(self) -> float:
        """Returns the battery current in Amps."""
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

    # Additional properties
    @property
    def firmware_version(self) -> str:
        """Returns the firmware version."""
        return self._data.get('FW', 'Unknown')

    @property
    def state_of_operation(self) -> str:
        """Returns the state of operation as a descriptive string."""
        cs_code = int(self._data.get('CS', '0'))
        cs_states = {
            0: 'Off',
            2: 'Fault',
            3: 'Bulk',
            4: 'Absorption',
            5: 'Float'
        }
        return cs_states.get(cs_code, 'Unknown')

    @property
    def off_reason(self) -> list:
        """Returns a list of active off reasons."""
        or_code_hex = self._data.get('OR', '0')
        try:
            or_code = int(or_code_hex, 16)
        except ValueError:
            or_code = 0
        reasons = []
        for bitmask, reason in self.OFF_REASON_CODES.items():
            if or_code & bitmask:
                reasons.append(reason)
        return reasons if reasons else ['Unknown']

    @property
    def error_code(self) -> str:
        """Returns the error description."""
        err_code_str = self._data.get('ERR', '0')
        try:
            err_code = int(err_code_str)
        except ValueError:
            err_code = -1  # Undefined error code
        return self.ERROR_CODES.get(err_code, f'Unknown error code: {err_code}')

    @property
    def load_state(self) -> str:
        """Returns the load state (ON/OFF)."""
        return self._data.get('LOAD', 'Unknown')

    @property
    def load_current(self) -> float:
        """Returns the load current in Amperes."""
        return mA(self._data.get('IL', '0'))

    @property
    def yield_total(self) -> float:
        """Returns the total yield in kWh."""
        return float(self._data.get('H19', '0')) / 100

    @property
    def yield_today(self) -> float:
        """Returns today's yield in kWh."""
        return float(self._data.get('H20', '0')) / 100

    @property
    def maximum_power_today(self) -> float:
        """Returns today's maximum power in Watts."""
        return float(self._data.get('H21', '0'))

    @property
    def yield_yesterday(self) -> float:
        """Returns yesterday's yield in kWh."""
        return float(self._data.get('H22', '0')) / 100

    @property
    def maximum_power_yesterday(self) -> float:
        """Returns yesterday's maximum power in Watts."""
        return float(self._data.get('H23', '0'))

    @property
    def day_sequence_number(self) -> int:
        """Returns the day sequence number."""
        return int(self._data.get('HSDS', '0'))

    @property
    def product_id(self) -> str:
        """Returns the product ID."""
        return self._data.get('PID', 'Unknown')

if __name__ == '__main__':
    try:
        v = VEDirect()
        print(f"Firmware Version: {v.firmware_version}")
        print(f"Serial Number: {v.device_serial}")
        print(f"Battery Voltage: {v.battery_volts} V")
        print(f"Battery Current: {v.battery_amps} A")
        print(f"Solar Voltage: {v.solar_volts} V")
        print(f"Solar Power: {v.solar_power} W")
        print(f"State of Operation: {v.state_of_operation}")
        print(f"MPPT State: {v.device_MPPT_state.name}")
        print("Off Reasons:")
        for reason in v.off_reason:
            print(f"- {reason}")
        print(f"Error Code: {v.error_code}")
        print(f"Load State: {v.load_state}")
        print(f"Load Current: {v.load_current} A")
        print(f"Total Yield: {v.yield_total} kWh")
        print(f"Yield Today: {v.yield_today} kWh")
        print(f"Maximum Power Today: {v.maximum_power_today} W")
        print(f"Yield Yesterday: {v.yield_yesterday} kWh")
        print(f"Maximum Power Yesterday: {v.maximum_power_yesterday} W")
        print(f"Day Sequence Number: {v.day_sequence_number}")
        print(f"Product ID: {v.product_id}")
    except VEDirectException as e:
        print(f"Error: {e}")

