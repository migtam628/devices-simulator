# Barcode Keyboard Input Simulation on macOS

The previous IOHIDUserDevice-based helper produced “Virtual HID did not report READY” on some Macs. v0.6 replaces it with **Quartz keyboard events**, requiring user-approved macOS Accessibility access. This is **not a virtual HID device or a flatbed scanner** and does not appear in Printers & Scanners.

Use **System Integration → Barcode Input Simulator → Enable Keyboard Mode**, approve Accessibility permission if requested, then send a test barcode with a 3-second delay into an empty TextEdit document. If access was just granted, relaunch the app. Test keyboard input in a scratch document only; no real USB/HID device is created.

See [v0.6 release notes](RELEASE_V0_6.md) for limits, including the still-unimplemented eSCL/AirScan scanner and true HID driver.
