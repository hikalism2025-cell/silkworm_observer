# Kaiko Camera Packaging Notes

## Files to install
- `/usr/lib/kaiko-camera/app_qt_v2.py`
- `/usr/lib/kaiko-camera/kaiko_updater_service.py`
- `/usr/bin/kaiko-camera`
- `/usr/share/applications/kaiko-camera.desktop`
- `/usr/share/dbus-1/system-services/com.kaiko.Updater.service`
- `/usr/lib/systemd/system/kaiko-updater.service`
- `/usr/share/polkit-1/actions/com.kaiko.updater.policy`
- `/etc/polkit-1/rules.d/60-kaiko-updater.rules`
- `/etc/kaiko-camera/updater.json`

## Operator group
```bash
sudo groupadd -f kaiko-operators
sudo usermod -aG kaiko-operators <operator_user>
```

## Enable updater service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kaiko-updater.service
```

## Update config
Create `/etc/kaiko-camera/updater.json`:
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
