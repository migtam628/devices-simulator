# Devices Simulator v0.13.3 — bounded POSIX serial subscriptions

- **New:** Opt-in `SUB` / `UNSUB` support on macOS/Linux pseudo-terminal scale endpoints, with 500 ms polling and live `EVT` readings.
- **Limits:** 30 seconds or 60 weight frames per subscription, explicit `UNSUB OK`, graceful `EVT END LIMIT`, non-blocking PTY writes and backpressure shutdown.
- **Compatibility:** Prior read-only commands `S`, `SI`, `I0`, `I2`, `I3`, `I4` are unchanged. TCP streaming remains available.
- **Tests:** Genuine POSIX PTY event tests, simulator value updates, injected busy condition, unsubscribe, expiry, reconnect and command regression.
- **Scope:** Development fixture only; POSIX PTY is not USB, BLE, Windows COM, manufacturer-certified hardware or standard MT-SICS SIR.
- **Unresolved:** Windows COM driver, native USB/BLE emulation, cross-platform physical-OS compatibility, macOS CUPS end-to-end JPG capture.

GitHub CI is expected to validate code on Ubuntu and packaging matrices after merge; real-device/customer acceptance is separate.
