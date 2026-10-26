# macOS CoreHID POS Scale — experimental developer preview

## What has been implemented

- A six-byte USB HID POS input report codec (ID 3, status, units, exponent, weight).
- An opt-in Swift CoreHID virtual scale helper for macOS 15+.
- Activate, Check enumeration, and Deactivate controls in the scale detail view.
- Existing tare, gross weight, stable/unstable and over-capacity fixtures can dispatch HID reports when active.
- State distinguishes helper unavailable, helper running, and separately verified macOS HID enumeration.

## Important limitation

Apple CoreHID virtual-device creation requires an approved HID virtual-device entitlement and correct code signing. Ordinary unsigned GitHub builds DO NOT automatically have that entitlement, and can fail to activate. Accessibility approval or sudo does not substitute for entitlement. A successful build and tests DO NOT prove that the external OS recognizes a scale.

This is a generic Devices Simulator POS Scale and DOES NOT impersonate the DYMO USB vendor/product identity. An application requiring exact DYMO VID/PID will not recognize it as an M10. Apps that recognize HID POS Scale usage page 0x8D may work only after actual OS enumeration.

## Test on your Mac

1. Use the macOS version of the experimental Devices Simulator build.
2. Create or open a DYMO M10 shipping scale profile with USB HID selected.
3. In CoreHID POS Scale, click Activate and explicitly confirm.
4. If the app reports an entitlement or OS error, native activation is blocked. Do not claim the scale is installed.
5. If the helper activates, click Check macOS enumeration. The app uses a separate hidutil process to look for Devices Simulator POS Scale.
6. Open Terminal and run: hidutil list
7. If enumerated, generate a scale weight and verify your external HID POS test app can receive it.
8. Deactivate when finished. The virtual scale does not survive helper exit.

## Standalone helper self-test (build check only)

    swiftc -parse-as-library -O packaging/macos/scale_corehid.swift -o /tmp/mac_scale_corehid
    /tmp/mac_scale_corehid --self-test

## Report format

| Byte | Meaning |
|---|---|
| 0 | ID 3 |
| 1 | status: 2 zero, 3 unstable, 4 stable, 6 over capacity |
| 2 | unit: 2 grams |
| 3 | power of ten exponent: 0 |
| 4–5 | unsigned little-endian integer grams, 2 g resolution |

This minimal prototype does not yet respond to HID feature reports, and is NOT a certified commercial or legal-for-trade scale.

## Research references

- [Apple CoreHID virtual device](https://developer.apple.com/documentation/corehid/creatingvirtualdevices)
- [Apple virtual HID entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.hid.virtual.device)
- [USB-IF POS Usage Tables](https://www.usb.org/sites/default/files/pos1_02.pdf)
- [DYMO M10 specifications](https://www.dymo.com/scales/dymo-m5-m10-digital-postal-scales/SAP_1772057.html)

## Next steps

Validate an Apple-approved entitlement on a signed app, add feature reports, confirm external app behavior, then investigate Windows and Linux native adapters.
