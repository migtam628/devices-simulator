# Devices Simulator v0.15.1 — Zebra raw ZPL IPP capture

- Advertises `application/vnd.zebra-zpl` on Zebra's IPP printer attributes only.
- Accepts explicit ZPL MIME, `application/octet-stream` detection, and constrained `application/vnd.cups-raw` on Zebra.
- Allows Print-Job and Create-Job/Send-Document to save original.zpl and a genuine JPG image.
- Rejects ZPL on Brother, mismatched MIME versus payload, unsupported printer languages and invalid raw inputs with IPP errors.
- Adds socket-level IPP roundtrip tests, job status, diagnostics, JPG pixels and existing PDF job regression checks.
- README, raw ZPL guide and GitHub Pages download version updated.

This does NOT verify PrintNode Client routing, CUPS raw forwarding, real Windows/macOS OS print paths, or physical Zebra compatibility. Production driver certification and signed installers remain outside this release.
