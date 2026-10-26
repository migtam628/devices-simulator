# Device catalog and transport architecture — v0.7

## What was researched
A device **category**, **manufacturer/model**, and **connection transport** are separate entities. Example: a USB HID postal scale is not interchangeable with a BLE Weight Scale Service (WSS) peripheral or a serial-over-Ethernet shipping scale. The app stores these explicitly and validates combinations.

| Category | Sample manufacturer / model | Transport options (reference) | Simulator availability |
|---|---|---|---|
| Shipping scale | DYMO M10, M25 | USB HID | In-app weight reading; USB enumeration not implemented |
| Shipping scale | METTLER TOLEDO BC Shipping Scale | RS-232, USB serial, Bluetooth serial, Ethernet serial | In-app weight fixture; serial protocol responder not implemented |
| Weight scale | Bluetooth SIG WSS Generic | BLE GATT 0x181D / 0x2A9D | In-app fixture; BLE advertising/indications not implemented |
| Office printer | Brother HL-L2460DW | USB / network / IPP | Existing generic office capture; model-specific printer language not emulated |
| Thermal label printer | Zebra ZD421 | USB, optional Ethernet/serial, BLE setup | Existing generic 4×6 preview; limited ZPL |
| Label printer | Brother QL-1110NWB | USB, wired/wireless network, Bluetooth Classic | Catalog only; Brother raster protocol not implemented |
| Barcode scanner | Zebra DS2208 | USB HID / serial | macOS keyboard input simulator only; not an installed DS2208 |
| Receipt printer | Epson TM-T88VII | USB / network / optional serial | Profile only; ESC/POS adapter not implemented |
| Other peripherals | Generic USB, BLE, network, RFID, sensor, serial | Profile-specific | Catalog/profile-only |

**References** (manufacturer/product documents, not simulator compatibility certifications):

- USB-IF [HID specifications and POS usage tables](https://www.usb.org/hid), [POS usage reference](https://www.usb.org/integrated-usage-table-documents)
- Bluetooth SIG [Weight Scale Service 1.0.1](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/WSS_v1.0.1/out/en/index-en.html)
- DYMO [M10/M25 USB HID specifications](https://download.dymo.com/UserManuals/digitalscales/W008021_USBPostalScales_NA.pdf)
- METTLER TOLEDO [BC scale service manual](https://www.mt.com/dam/ind/IND_PDF/30126862_R02_BC_Scale_SM_EN.pdf)
- [Zebra ZD421 product specification](https://www.zebra.com/us/en/products/printers/desktop/zd400-series/zd421.html)
- [Brother HL-L2460DW](https://www.brother-usa.com/p/laser-printers/HLL2460DW)
- [Brother QL-1110NWB](https://www.brother-usa.com/p/desktop-label-printers/QL1110NWB)
- [Zebra DS2208 support](https://www.zebra.com/ap/en/support-downloads/scanners/general-purpose-scanners/ds2200-series.html)
- [Epson TM-T88VII documentation](https://mediaserver.goepson.com/ImConvServlet/imconv/93938a326f949a1b2bc0a47bb18db8b1518999dd/original?assetDescr=OmniLink_TM-T88VII_Specification_Sheet_CPD-61180R1.pdf)

## v0.7 implemented

- `device_catalog.py`: normalized categories and curated model profiles, with allowed transports, capability notes, sources, and selection validation.
- In the **Create Device wizard**: choose a type, then brand, model, transport, name, and device-specific settings.
- In **My Devices → Manage**: saved model and connection can be changed later without modifying OS registrations.
- Shipping scale in-app fixture: gross kg, tare kg, kg/lb/g/oz output, stable/unstable and over-capacity statuses, last reading persisted in the local JSON store.
- HTTP routes: `GET /api/catalog`, `POST /api/devices/{id}/model`, and `POST /api/devices/{id}/scale-reading`. Existing local token is required for mutating actions.

Example request, using the existing hub token:

```json
{"gross_kg": 2.25, "tare_kg": 0.1, "unit": "lb", "stable": true}
```

The response includes `scope: "in_app_scale_fixture"` and `transport_status: "not_connected"`. It **does not** claim the measurement was sent over USB, BLE or TCP.

## Next transport adapters (separate engineering work)

1. **USB-HID POS scale**: correct HID report descriptor, unit exponent, stable/unstable/out-of-range status, Windows Virtual HID Framework signed driver / Linux USB gadget or uinput where appropriate; research macOS entitlement-supported virtual HID path. USB-HID requires actual OS support, not renaming a profile.
2. **BLE GATT**: real peripheral advertisement, Weight Scale Service + required characteristics/indications, Bluetooth permissions, OS pairing and bond behavior. Standard WSS is mainly consumer health/fitness, not automatically suitable for carrier shipping scales.
3. **Serial / USB CDC / Bluetooth Classic**: per-vendor command-response adapters such as MT-SICS, port lifecycle, baud rate, error injection, pseudo-terminals on Unix and Windows virtual COM drivers.
4. **Network TCP**: localhost-only TCP test server for supported vendor protocols, optional explicit opt-in LAN exposure, connection/session telemetry, robust port conflicts and security.
5. **Printer/scanner specializations**: model-specific renderers/status codes, real eSCL/WIA scanner backends, ESC/POS, full Zebra command compatibility.

Do not spoof vendor USB VID/PIDs without research and explicit user intent; a selectable model only means *reference metadata* until its protocol adapter is implemented. Model names and trademarks belong to their owners.

## Source extension pattern

Add a tested entry to `MODELS` in `src/lulwa_virtual_printer/device_catalog.py` with the real category, verified manufacturer/model name, allowed transports, source URL and a clear capability note. Include `DEFAULT_MODEL` only when defining a new device category/preset. Never mark `transport_status` as connected until the native adapter can prove it.
