# v0.13.2 — Cross-platform test reliability

- Increased Windows-friendly Node.js syntax-check subprocess timeouts while still checking return codes.
- Extended local HTTP smoke test socket timeouts for heavily loaded CI runners.
- No changes to production listener behavior or supported protocols.
- Main features remain v0.13.0 Studio-managed TCP read and v0.13.1 opt-in 2Hz TCP subscription.

Windows CI still needs to pass before considering the release verified.