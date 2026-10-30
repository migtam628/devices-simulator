# OS Printer → IPP → JPG reliability (v0.14.1)

Devices Simulator has two distinct print paths:

- **In-app capture:** demo and Studio call the capture engine directly. A local JPG proves only local rendering.
- **Operating-system printing:** an installed CUPS printer queue sends a job to the **loopback-only IPP** service on `127.0.0.1:8631`, which invokes the same renderer and saves the JPG to the configured output root. OS queue registration alone **does not** prove this path works.

## One-click readiness in the app

Go to **System Integration** and choose **Check print path** beside Brother or Zebra. This read-only test reports:

| Check | Meaning | When blocked |
|---|---|---|
| Platform | Linux/macOS CUPS or experimental Windows PrintDocument | Windows must have a supported GDI-capable printer driver |
| Queue | Exact named OS queue points to the expected simulator IPP URI | Register the queue after starting the service; resolve conflicts rather than overwriting a real printer |
| IPP service | `http://127.0.0.1:8631/diagnostics` responds and reports output root | Start Devices Simulator; investigate other processes occupying 8631 |
| Output directory | IPP's **resolved output root exactly matches** the Hub's resolved output root | Stop stale IPP service and start both applications with the same `--output` path |
| Queue enabled | CUPS `lpstat` reports enabled, or Windows Print Spooler reports a non-offline queue | Enable the test queue and check the Print Spooler; never modify unrelated printer queues |
| Windows Spooler | Windows `Get-Service Spooler` reports Running | Start/repair the Windows Print Spooler service before sending test pages |

The endpoint `POST /api/system/print-readiness` with `{"preset":"zebra"}` or `{"preset":"brother"}` uses the existing local Hub token. It does not run `lp`, write data, change printer settings or generate JPGs. The authenticated `POST /api/system/print-test` still requires `confirm:true`; it refuses to run if readiness is blocked. This test produces a uniquely marked PDF and verifies that a matching job.json plus nonempty JPG appeared. An accepted spool request is **not** success until the JPG exists.

## Manual verification (Linux / macOS)

Start the app (both Hub and IPP servers need to be running), then run:

```bash
curl -fsS http://127.0.0.1:8631/healthz
curl -fsS http://127.0.0.1:8631/diagnostics
lpstat -v Lulwa_SIM_Brother
lpstat -v Lulwa_SIM_Zebra_4x6
lpstat -p Lulwa_SIM_Brother -l
lpstat -p Lulwa_SIM_Zebra_4x6 -l
```

For the app's **exact matching JPG check**, use **Verify OS Print → JPG**. It submits its own safe sample through the selected queue. It will not send a real order, update shipment state, or touch physical devices. For a manual queue smoke test, create a simple one-page PDF and use `lp -d Lulwa_SIM_Zebra_4x6 -t os-debug-label sample.pdf`. Check the **IPP service's** reported output directory for `zebra/*/job.json` and `page-001.jpg`. Brother uses `brother-tray1/` or `brother-tray2/`.

If files are missing, inspect `/diagnostics` for `capture_status` and `ipp_status` alongside each job. A **missing print event** indicates spooler/queue routing rather than a renderer failure; a **failed capture event** indicates format/rendering/storage issues. `lpstat -t`, `lpstat -W not-completed` and CUPS `error_log` can reveal a stuck queue. Cancel only the relevant test job, not an unrelated user's job. Do not treat CUPS acceptance as delivery.

## CI integration

GitHub's **Test** workflow has two gates: ordinary `pytest` and **CUPS OS print-to-JPG roundtrip (Linux)**. The CUPS gate installs a real scheduler, starts a local IPP simulator, creates `-m everywhere` queues for the two presets, prints unique PDF samples via `lp`, and verifies the created job's JPG. Failure prints recent IPP metadata, CUPS queue state and local spooler logs. The script lives at `tests/cups_roundtrip_smoke.py`.

**Verified:** Ubuntu 22.04 CI CUPS → IPP → JPG for Brother and Zebra. **Not established:** real macOS queue driver behavior, Windows spooler support, PrintNode integration, native hardware printers or customer-specific third-party applications. This is not IPP Everywhere certification and makes no claim about physical shipping.

## Windows native queue test (experimental v0.14.1)

On **System Integration**, check the path for the simulator Brother or Zebra queue first. The Windows checks use `Get-Service -Name Spooler` and `Get-Printer -Name <simulator_queue>` without making changes. The app also attempts to read `Get-PrinterPort` properties for an exact IPP URL match. **Some Windows IPP ports hide their endpoint**; if so, the queue is marked unverified and the test is deliberately blocked. A local host address alone is insufficient proof that the queue points to the simulator.

When the queue is exactly verified, **Verify OS Print → JPG** runs a single native `System.Drawing.Printing.PrintDocument` GDI sample (no silent print to another printer). The queue receives a unique `DS-OS-TEST-...` job name and page text. This operation is only triggered by explicit confirmation. Check `/diagnostics` for IPP Print-Job or Send-Document events and the MIME `document_format` field.

A successful Windows spooler submission **does not prove JPG success**. A JPG is reported only after the simulator persists the unique matching job with nonempty JPG files. A Windows IPP class driver might send PWG Raster, XPS, or another format the experimental PDF/JPEG/PNG renderer does not support; in that case the simulator will return an explicit diagnostic. It does not silently convert data or claim broad support.

Windows PowerShell troubleshooting (read-only):

```powershell
Get-Service -Name Spooler
Get-Printer -Name 'Lulwa_SIM_Brother' | Format-List Name,PortName,PrinterStatus,WorkOffline
Get-Printer -Name 'Lulwa_SIM_Zebra_4x6' | Format-List Name,PortName,PrinterStatus,WorkOffline
Get-PrinterPort | Where-Object { $_.Name -match 'IPP' } | Format-List Name,PrinterHostAddress,Description
Invoke-RestMethod http://127.0.0.1:8631/diagnostics
```

If the queue's actual URL cannot be proven, do not print until an exact local endpoint is verified. The tested queues are experimental and **not physical Brother/Zebra drivers**; no remote or physical printer should receive a sample.

**Current evidence:** Code-level and syntax tests for Windows; genuine Ubuntu CUPS → IPP → JPG smoke tests for both printer profiles. No successful physical Windows IPP print-to-JPG roundtrip has been independently observed yet.
