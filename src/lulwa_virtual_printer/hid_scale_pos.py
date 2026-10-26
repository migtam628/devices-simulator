"""Generic USB HID Point-of-Sale scale data report (usage page 0x8D).

This encoder does NOT install or impersonate physical USB hardware.
USB-IF HID POS usage tables: report ID 3, status, units, scaling and weight.
"""
import math
import struct

REPORT_ID=3
STATUS={"fault":1,"zero":2,"unstable":3,"stable":4,"negative":5,"over_capacity":6}
UNITS={"g":0x02,"kg":0x03,"oz":0x0B,"lb":0x0C}
REPORT_DESCRIPTOR=bytes([
  0x05,0x8D,0x09,0x20,0xA1,0x01,
  0x09,0x32,0xA1,0x02,0x85,0x03,
  0x09,0x70,0x15,0x01,0x25,0x08,
  0x75,0x08,0x95,0x01,0x81,0x00,
  0x09,0x50,0x15,0x01,0x25,0x0C,
  0x75,0x08,0x95,0x01,0x81,0x00,
  0x09,0x41,0x15,0x81,0x25,0x7F,
  0x75,0x08,0x95,0x01,0x81,0x02,
  0x09,0x40,0x15,0x00,0x26,0xFF,0x7F,
  0x75,0x10,0x95,0x01,0x81,0x02,
  0xC0,0xC0
])

def encode_weight_report(net_kg: float, *, stable=True, capacity_kg=4.5) -> bytes:
    """6 bytes: report id, status, gram unit, exponent 0, LE16 grams.

    Rounds to 2g resolution. Generic POS report, not a copied DYMO descriptor.
    """
    if type(stable) is not bool:
        raise ValueError("stable must be bool")
    if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (net_kg,capacity_kg)):
        raise ValueError("Weight/capacity must be finite numbers")
    if net_kg < 0 or capacity_kg <= 0:
        raise ValueError("Weight must be nonnegative and capacity positive")
    status=STATUS["over_capacity"] if net_kg>capacity_kg else (
        STATUS["unstable"] if not stable else STATUS["zero"] if net_kg==0 else STATUS["stable"])
    grams=min(32767,max(0,round(net_kg*500)*2))
    return struct.pack("<BBBBH",REPORT_ID,status,UNITS["g"],0,grams)

def decode_weight_report(report: bytes) -> dict:
    if not isinstance(report,bytes) or len(report)!=6 or report[0]!=REPORT_ID:
        raise ValueError("Expected six-byte HID POS scale input report")
    _,status,unit,exponent,raw=struct.unpack("<BBBBH",report)
    if unit not in UNITS.values():
        raise ValueError("Unknown unit")
    if exponent>=128: exponent-=256
    return {"report_id":REPORT_ID,"status_code":status,"unit_code":unit,
            "exponent":exponent,"raw_weight":raw,
            "weight_g":raw*10**exponent if unit==UNITS["g"] else None}
