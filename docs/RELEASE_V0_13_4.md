# Devices Simulator v0.13.4 — Advanced Studio managed serial scale

Advanced Studio's new **Serial Scale** node reads a real, already activated macOS/Linux virtual serial (PTY) endpoint.

- Create a saved scale profile with RS-232/serial transport and manually activate it in Connections. Select the **External Serial Scale** template in Studio.
- The node sends one bounded `SI` command through the real OS PTY and validates the returned weight. No arbitrary serial paths or automatic endpoint activation.
- Unstable, busy, overload, missing/closed and timed-out responses produce actionable failed run traces; downstream steps skip.
- A streaming `SUB` session must first receive `UNSUB`. A serial PTY remains shared; concurrent unrelated readers may interfere.
- Adds POSIX PTY, validation, streaming-guard, fault and authenticated HTTP integration tests.
- No Windows COM, native USB/BLE, manufacturer-certified scale protocol or OS print-queue implementation is claimed.
- Portable desktop archives remain unsigned experimental builds. Validate on real macOS/Linux installations before operational acceptance.
