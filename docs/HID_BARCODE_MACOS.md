# Experimental macOS virtual HID barcode scanner

**Not a flatbed scanner and not a USB device.** A barcode HID scanner behaves like a keyboard and does **not** appear in macOS Printers & Scanners. The app creates a temporary virtual keyboard using macOS IOKit `IOHIDUserDevice`; it exists only while activated and while Devices Simulator remains open.

## Test on a Mac
1. Download a fresh macOS Apple Silicon/Intel app from [GitHub Actions](https://github.com/migtam628/devices-simulator/actions/workflows/build-desktop.yml), extract and open it.
2. Go to **Create Device → HID Barcode Scanner**, or **System Integration → Virtual HID Barcode Scanner**.
3. Click **Activate Virtual HID**. Grant any macOS permissions requested; unsupported or denied creation reports an error.
4. Open a blank TextEdit document, but return to Devices Simulator to enter `LULWA1001`.
5. Click **Send barcode in 3 seconds**, confirm, then click into TextEdit before the timer finishes. Characters should appear in the focused text field as though typed by a barcode reader.
6. Click **Deactivate HID** to stop the virtual keyboard.

**Caution:** The virtual keyboard sends keystrokes to whatever application has focus. Do not focus a terminal, password box, payment field, or other sensitive input during a test. Only ASCII letters, digits, hyphen, underscore, dot and slash are accepted (1–100 chars; US keyboard layout).

## Limitations
- **macOS:** experimental runtime HID keyboard; GitHub Actions compiles and smoke-tests the helper but cannot verify actual keyboard entry on your Mac. “HID active” means the helper reported creation, not independent OS device enumeration.
- **Windows:** virtual HID driver not implemented.
- **Linux:** virtual HID through `uinput` is planned, with OS permissions needed.
- **Document scanners:** separate eSCL/AirScan service on macOS required to appear in Printers & Scanners; not implemented.
- **No permanent installation:** helper disappears when app stops. It does not impersonate a physical USB scanner or vendor VID/PID.

To inspect possible HID device enumeration while active:
```bash
ioreg -r -c IOHIDDevice -l | grep -B 8 -A 12 'Lulwa SIM Barcode HID'
```
Some macOS versions may use a different IOKit class; the end-to-end TextEdit test is more useful.

Code: `packaging/macos/hid_scanner.c`, `src/lulwa_virtual_printer/hid_barcode.py`.

References: [Apple virtual HID](https://developer.apple.com/documentation/corehid/creatingvirtualdevices), [Apple IOHIDUserDevice sample](https://github.com/aosm/IOHIDFamily/blob/master/tools/IOHIDUserDeviceTest.c).
