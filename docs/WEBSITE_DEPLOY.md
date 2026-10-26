# Publish the Devices Simulator product website

The complete static site is already included in the repository:

- Product page: [docs/index.html](index.html)
- Styles: [docs/site.css](site.css)
- Illustrations: [docs/assets/](assets/)
- Download CTAs: point directly to the project's GitHub Releases
- Support and business inquiries: GitHub Issues

No framework, package manager or cloud service is required to view this page.

## Local preview

From the repository root:

    python3 -m http.server 8000 --directory docs

Open http://localhost:8000/. This hosts only the static files and does not expose the local print simulator service.

## Publish using GitHub Pages

**Repository setting required (one-time by the repository owner):**

1. Open the repository on GitHub and select **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch **main** and directory **/docs**.
4. Save, then wait for GitHub to generate the Pages URL.
5. Open the published URL and verify the mobile view, illustrations, downloads, links, FAQ, and content.

For a standard project repository, GitHub Pages commonly uses an address like:
**https://migtam628.github.io/devices-simulator/**

That is the **expected URL format**, not confirmation that Pages has been enabled or deployed. Before announcing the website publicly, verify the actual URL in Settings → Pages.

Optional: Later add a company domain by following GitHub Pages custom-domain verification instructions; do not change DNS until you own/control the domain.

## Marketing asset integrity

The current SVG product previews are **illustrations**, not actual app screenshots. Replace or supplement them with redacted screenshots taken from tested operating systems after verifying device registration, output capture and diagnostics.

Recommended screenshot subjects:

- Hub Home showing sample profiles only
- Brother tray configuration
- Zebra 4 × 6 label configuration
- Output Gallery with generic/noncustomer JPG
- Diagnostics with a successful trace
- Studio shipping-station demo

Never publish real customer addresses, carrier barcodes, print payloads, credentials, access tokens, OS usernames, or internal endpoints.

## Before promoting to companies

- Clarify and publish the project's **software license** or provide explicit enterprise terms.
- Verify the v0.6.1 CUPS pipeline on real macOS and Linux devices, as CI tests alone don't certify host support.
- Confirm release downloads are current, signed installers are not yet available, and supported platform statuses are not overstated.
- Review data retention, security, privacy policy, support process and commercial contact options.
