# Release & Update Rules

This document defines versioning, `latest.json` format, and GitHub Releases procedure.

## Versioning
- Use semantic versioning: `MAJOR.MINOR.PATCH`
- Increment:
  - PATCH: bug fixes, UI tweaks
  - MINOR: new features (backward compatible)
  - MAJOR: breaking changes

## `latest.json` format
Place `latest.json` at repository root (main branch):

```json
{
  "version": "1.2.3",
  "deb_url": "https://github.com/hikalism2025-cell/silkworm_observer/releases/download/v1.2.3/kaiko-camera_1.2.3_arm64.deb",
  "sha256": "PUT_SHA256_HERE"
}
```

Rules:
- `version` must match the release tag (e.g., `v1.2.3`)
- `deb_url` must point to the .deb uploaded to the release
- `sha256` is the SHA256 checksum of the .deb file

## GitHub Releases procedure
1. Update `debian/changelog` version (e.g., `0.1.0-1` -> `1.2.3-1`).
2. Build `.deb` on Raspberry Pi (arm64).
3. Compute SHA256 of the .deb.
4. Create GitHub Release with tag `vX.Y.Z` and upload the `.deb`.
5. Update `latest.json` in `main` with the new version, URL, and checksum.

## Example commands (on Raspberry Pi)
```bash
# build
dpkg-buildpackage -us -uc

# sha256
sha256sum ../kaiko-camera_1.2.3-1_arm64.deb
```
