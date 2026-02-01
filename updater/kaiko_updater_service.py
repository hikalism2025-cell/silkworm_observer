import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

SERVICE_NAME = "com.silkworm.ObserverUpdater"
OBJECT_PATH = "/com/silkworm/ObserverUpdater"
INTERFACE = "com.silkworm.ObserverUpdater"

CONFIG_PATH = Path("/etc/silkworm-observer/updater.json")
DEFAULT_LATEST_URL = "https://raw.githubusercontent.com/hikalism2025-cell/silkworm_observer/main/latest.json"
DOWNLOAD_PATH = Path("/var/tmp/silkworm-observer_update.deb")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"latest_url": DEFAULT_LATEST_URL}


def get_installed_version() -> str:
    try:
        result = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Version}", "silkworm-observer"],
            text=True,
        )
        return result.strip()
    except Exception:
        return "0.0.0"


def is_newer_version(latest: str, current: str) -> bool:
    result = subprocess.run(["dpkg", "--compare-versions", latest, "gt", current])
    return result.returncode == 0


def fetch_latest(latest_url: str) -> dict:
    with urllib.request.urlopen(latest_url, timeout=15) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)


def download_file(url: str, dest: Path) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    dest.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def install_deb(path: Path) -> tuple[bool, str]:
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    result = subprocess.run(
        ["apt-get", "install", "-y", str(path)],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, "更新が完了しました。アプリを再起動してください。"
    return False, result.stderr.strip() or "更新に失敗しました。"


class UpdaterService(dbus.service.Object):
    def __init__(self, bus: dbus.Bus) -> None:
        super().__init__(bus, OBJECT_PATH)
        self.bus = bus

    @dbus.service.method(INTERFACE, in_signature="", out_signature="(bs)")
    def CheckUpdate(self) -> tuple[bool, str]:
        config = load_config()
        latest_info = fetch_latest(config["latest_url"])
        latest = latest_info.get("version", "0.0.0")
        current = get_installed_version()
        if is_newer_version(latest, current):
            return True, f"更新があります: {current} -> {latest}"
        return False, f"最新です: {current}"

    @dbus.service.method(INTERFACE, in_signature="", out_signature="(bs)", sender_keyword="sender")
    def InstallUpdate(self, sender: str) -> tuple[bool, str]:
        if not self._check_authorization(sender):
            return False, "権限がありません。"
        config = load_config()
        latest_info = fetch_latest(config["latest_url"])
        latest = latest_info.get("version", "0.0.0")
        deb_url = latest_info.get("deb_url", "")
        sha256 = latest_info.get("sha256", "")
        if not deb_url:
            return False, "deb_url が見つかりません。"
        current = get_installed_version()
        if not is_newer_version(latest, current):
            return False, f"最新です: {current}"

        DOWNLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
        actual_hash = download_file(deb_url, DOWNLOAD_PATH)
        if sha256 and sha256 != actual_hash:
            return False, "ハッシュ検証に失敗しました。"

        success, message = install_deb(DOWNLOAD_PATH)
        return success, message

    def _check_authorization(self, sender: str) -> bool:
        try:
            dbus_obj = self.bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
            dbus_iface = dbus.Interface(dbus_obj, "org.freedesktop.DBus")
            pid = dbus_iface.GetConnectionUnixProcessID(sender)
            result = subprocess.run(
                [
                    "pkcheck",
                    "--action-id",
                    "com.silkworm.observer.install",
                    "--process",
                    str(pid),
                    "--allow-user-interaction",
                    "false",
                ]
            )
            return result.returncode == 0
        except Exception:
            return False


def main() -> None:
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    dbus.service.BusName(SERVICE_NAME, bus=bus)
    UpdaterService(bus)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
