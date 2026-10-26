# macOS CUPS Print → JPG diagnosis (v0.8.1)

## Why an installed printer may not save JPG output

Mac printers can appear in System Settings while print jobs still fail. A prior IPP server implementation rejected chunked HTTP uploads without Content-Length, contrary to the IPP transport requirement. Version 0.8.1 now reads bounded chunked transfers, records HTTP framing failures, and tracks CUPS status polls. Actual behavior must be verified on your Mac.

## Test on macOS

1. Install v0.8.1 and quit the older Devices Simulator completely.
2. Launch the updated app and leave it running.
3. In Terminal:

       curl -s http://127.0.0.1:8631/healthz | python3 -m json.tool
       lpstat -v Lulwa_SIM_Zebra_4x6
       lpstat -p Lulwa_SIM_Zebra_4x6 -l
       lpstat -o Lulwa_SIM_Zebra_4x6

4. In macOS print queue, cancel the previously stuck simulator test job. If you intentionally want to clear **all jobs in the simulated Zebra queue only**, use:

       cancel -a Lulwa_SIM_Zebra_4x6

   For Brother, replace the queue name with Lulwa_SIM_Brother. Never run cancel -a on real printers you want to preserve.
5. In Devices Simulator, open System Integration → Verify OS Print → JPG.
6. Check Output Gallery and the default folder:

       ~/Documents/Lulwa Virtual Printer/zebra/

   A successful test produces original.pdf, job.json, and page-001.jpg within a job folder.
7. If no JPG appears, inspect the diagnostic trace:

       curl -s http://127.0.0.1:8631/diagnostics | python3 -m json.tool

## Diagnostics reference

| Event | Interpretation |
|---|---|
| HTTP `http_rejected` | A malformed/unsupported HTTP upload did not reach IPP processing |
| `0x0005` awaiting_document | CUPS reserved a job; document not yet completed |
| `0x0002` / `0x0006` rendered | Print-Job / Send-Document captured a JPG |
| `0x0002` / `0x0006` failed | Rendering or document-format failure |
| `0x0009` state_9 | CUPS polled a completed job |
| `0x0009` state_3 | Job still pending without completed document |

The diagnostic JSON contains protocol/job metadata, not original customer documents. The output folder may contain sensitive address and label data; don't share it publicly.

Installed in OS means the spooler has the expected queue URI. End-to-end verification requires an actual JPG file and a completed IPP job.
