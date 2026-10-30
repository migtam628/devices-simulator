# OS Printer → IPP → JPG reliability (v0.14.0)

Devices Simulator has two distinct print paths:

- **In-app capture:** demo and Studio call the capture engine directly. A local JPG proves only local rendering.
- **Operating-system printing:** an installed CUPS printer queue sends a job to the **loopback-only IPP** service on `127.0.0.1:8631`, which invokes the same renderer and saves the JPG to the configured output root. OS queue registration alone **does not** prove this path works.

## One-click readiness in the app

Go to **System Integration** and choose **Check print path** beside Brother or Zebra. This read-only test reports:

| Check | Meaning | When blocked |
|---|---|---|
| Platform | Linux/macOS `lp` and CUPS verification supported | Windows verification is still outstanding |
| Queue | Exact named OS queue points to the expected simulator IPP URI | Register the queue after starting the service; resolve conflicts rather than overwriting a real printer |
| IPP service | `http://127.0.0.1:8631/diagnostics` responds and reports output root | Start Devices Simulator; investigate other processes occupying 8631 |
| Output directory | IPP's **resolved output root exactly matches** the Hub's resolved output root | Stop stale IPP service and start both applications with the same `--output` path |
| Queue enabled | `lpstat -p <printer> -l` succeeds and is not disabled | Enable queue, cancel a stuck job, and verify the scheduler is active |

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
