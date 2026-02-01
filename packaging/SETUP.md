# Kaiko Camera Packaging Notes

## Files to install
- `/usr/lib/silkworm-observer/app_qt_v2.py`
- `/usr/lib/silkworm-observer/kaiko_updater_service.py`
- `/usr/bin/silkworm-observer`
- `/usr/share/applications/silkworm-observer.desktop`
- `/usr/share/dbus-1/system-services/com.silkworm.ObserverUpdater.service`
- `/usr/lib/systemd/system/silkworm-updater.service`
- `/usr/share/polkit-1/actions/com.silkworm.observer.policy`
- `/etc/polkit-1/rules.d/60-silkworm-observer.rules`
- `/usr/share/silkworm-observer/updater.json.example`
- `/etc/silkworm-observer/updater.json`

## Operator group
```bash
sudo groupadd -f silkworm-operators
sudo usermod -aG silkworm-operators <operator_user>
```

## Enable updater service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now silkworm-updater.service
```

## Update config
Create `/etc/silkworm-observer/updater.json` (initially copied from `updater.json.example`):
```json
{
  "latest_url": "https://raw.githubusercontent.com/hikalism2025-cell/silkworm_observer/main/latest.json"
}
```

`latest.json` format:
```json
{
  "version": "1.2.3",
  "deb_url": "https://github.com/hikalism2025-cell/silkworm_observer/releases/download/v1.2.3/kaiko-camera_1.2.3_arm64.deb",
  "sha256": "PUT_SHA256_HERE"
}
```
