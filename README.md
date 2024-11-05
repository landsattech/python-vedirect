# python-VEDirect

## What is this lib ?
Small library to read Victron's VE.Direct frames.

This is useful in order to read Victron's MPPT charge controllers.

You need to use a VE.Direct to USB cable

## How to use this lib ?
First of all, install this library using pip:
```bash
pip3 install vedirect
```

Then, you simply need to import the lib and start asking values:
```python

>>> import vedirect
>>> device = vedirect.VEDirect()
>>> print(device.battery_volts)
27.5
```

Sample Output
```
Firmware Version: 159
Serial Number: HQ2414G4VHA
Battery Voltage: 13.65 V
Battery Current: -0.01 A
Solar Voltage: 0.01 V
Solar Power: 0.0 W
State of Operation: Off
MPPT State: Off
Off Reasons:
- No input power
Error Code: No error
Load State: ON
Load Current: 0.0 A
Total Yield: 0.0 kWh
Yield Today: 0.0 kWh
Maximum Power Today: 0.0 W
Yield Yesterday: 0.0 kWh
Maximum Power Yesterday: 0.0 W
Day Sequence Number: 0
Product ID: 0xA060

```
