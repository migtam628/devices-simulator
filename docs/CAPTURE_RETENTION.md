# Captured document retention (v0.14.3)

Devices Simulator saves source files, generated JPGs, and job metadata under
the configured local output directory. Files can contain customer addresses,
order identifiers, labels, and other sensitive data. **No captures are removed
automatically** and there is no server-side scheduled policy in this release.

## Manual workflow

Open **Settings → Capture retention**. Choose an age threshold (30, 90, 180 or
365 days) and click **Preview eligible captures**. The tool reports counts and
the approximate bytes eligible in the next batch, without displaying customer
data or reading document contents. After inspecting the report, choose
**Delete reviewed batch** and confirm permanent deletion.

The preview is a real dry-run. The cleanup needs the browser's local access
token, `confirm: true`, the same whole-number days, and the exact SHA-256
fingerprint returned by preview. A changed file causes the request to fail
rather than deleting a different set of captures. Each deletion is limited to
100 old job folders per request. For larger datasets, preview again after each
successful batch.

## Authenticated API

- `POST /api/system/retention/preview` with `{"days":90}` returns
  `preview.eligible_jobs`, `batch_jobs`, `batch_bytes`,
  `more_remaining`, and `fingerprint`.
- `POST /api/system/retention/cleanup` with
  `{"days":90,"fingerprint":"<preview fingerprint>","confirm":true}`
  returns `cleanup.deleted_jobs`, `deleted_bytes` and
  `remaining_jobs`.

These routes run only via the Hub's loopback server with its existing
X-Devices-Token authentication. Files are considered only when:
- under a known capture output profile, exactly one job directory deep;
- accompanied by parseable `job.json` with valid, timezone-aware age;
- the metadata's profile agrees with its containing profile directory;
- no symlinks are present anywhere inside the job directory;
- the directory and file manifest still match the reviewed preview.

Malformed entries, unknown directory layouts, missing files, future-dated
jobs and symlinked trees are excluded. The original documents and JPGs
are deleted together; **there is no undo**. Workflow run histories, OS
printer queues, local connected device settings and application code are
never modified. History links to deleted artifacts will no longer open.

For enterprise usage, retain only test data and apply your organization's
access controls, backups, retention policy and legal requirements. A local
purge is not secure erasure from flash media or backups. This feature does
not add account-based policy management or remote data deletion.
