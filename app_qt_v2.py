import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
from PyQt6 import QtCore, QtGui, QtWidgets
try:
    import dbus  # type: ignore[import-not-found]
except ImportError:
    dbus = None

try:
    from picamera2 import Picamera2  # type: ignore[import-not-found]
    from picamera2.encoders import H264Encoder  # type: ignore[import-not-found]
except ImportError:
    Picamera2 = None
    H264Encoder = None


class VideoLabel(QtWidgets.QLabel):
    def __init__(self, camera_id: int, parent=None) -> None:
        super().__init__(parent)
        self.camera_id = camera_id


class CameraRoiApp(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Raspberry Pi Camera ROI Tool (Qt)")

        self.camera_ids = (1, 2)
        self.cameras: dict[int, Picamera2] = {}
        self.is_running = False
        self.frames: dict[int, object] = {}

        self.display_w = 450
        self.display_h = 350
        self.save_path = Path("/home/miyauchi/images")
        self.video_save_path = Path("/home/miyauchi/videos")
        self.exp_name = "kaiko"
        self.video_length_seconds = 60 * 10
        self.video_interval_seconds = 0
        self.image_interval_seconds = 5
        self.camera_fps = 1
        self.frame_interval_ms = 1000
        self.recording = False
        self.record_thread = None
        self.image_capturing = False
        self.image_timer = QtCore.QTimer(self)
        self.image_timer.timeout.connect(self._capture_image_tick)
        self.camera_lock = threading.Lock()

        self._build_ui()
        self._setup_timer()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_layout = QtWidgets.QHBoxLayout(central)
        left_layout = QtWidgets.QVBoxLayout()
        right_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        toolbar = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.status_label = QtWidgets.QLabel("Stopped")

        self.preview_btn = QtWidgets.QPushButton("Preview")
        self.update_btn = QtWidgets.QPushButton("Update")

        toolbar.addWidget(self.start_btn)
        toolbar.addWidget(self.stop_btn)
        toolbar.addWidget(self.preview_btn)
        toolbar.addWidget(self.update_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.status_label)

        left_layout.addLayout(toolbar)

        video_container = QtWidgets.QHBoxLayout()
        self.video_labels: dict[int, VideoLabel] = {}
        for cam_id in self.camera_ids:
            cam_layout = QtWidgets.QVBoxLayout()
            cam_layout.addWidget(QtWidgets.QLabel(f"Camera {cam_id}"))
            label = VideoLabel(cam_id)
            label.setFixedSize(self.display_w, self.display_h)
            label.setStyleSheet("background: black;")
            cam_layout.addWidget(label)
            self.video_labels[cam_id] = label
            video_container.addLayout(cam_layout)
        left_layout.addLayout(video_container)

        self.mode_tabs = QtWidgets.QTabWidget()
        image_tab = QtWidgets.QWidget()
        self.mode_tabs.addTab(image_tab, "Image Capture")

        video_tab = QtWidgets.QWidget()
        self.mode_tabs.addTab(video_tab, "Video Recording")

        tab_bar = self.mode_tabs.tabBar()
        tab_font = tab_bar.font()
        tab_font.setPointSizeF(tab_font.pointSizeF() * 2.0)
        tab_bar.setFont(tab_font)
        metrics = QtGui.QFontMetrics(tab_font)
        sample_text = "Video Recording"
        base_width = metrics.horizontalAdvance(sample_text) + 32
        base_height = metrics.height() + 12
        self.mode_tab_width = int(base_width * 1.5)
        tab_bar.setStyleSheet(
            "QTabBar::tab {"
            f" min-width: {self.mode_tab_width}px;"
            f" min-height: {base_height * 3}px;"
            f" max-height: {base_height * 3}px;"
            f" height: {base_height * 3}px;"
            "}"
        )
        tab_bar.setFixedHeight(int(base_height * 3))
        self.mode_tabs.setFixedHeight(int(base_height * 3))

        left_layout.addWidget(self.mode_tabs)

        self.settings_stack = QtWidgets.QStackedWidget()

        image_settings = QtWidgets.QGroupBox("Image Settings")
        image_layout = QtWidgets.QFormLayout(image_settings)
        image_layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        image_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.image_interval_spin = QtWidgets.QSpinBox()
        self.image_interval_spin.setRange(1, 24 * 60 * 60)
        self.image_interval_spin.setValue(self.image_interval_seconds)
        image_row = QtWidgets.QHBoxLayout()
        image_row.addWidget(self.image_interval_spin)
        image_row.addStretch()
        image_layout.addRow("Interval (sec)", image_row)
        self.settings_stack.addWidget(image_settings)

        video_settings = QtWidgets.QGroupBox("Video Settings")
        video_layout = QtWidgets.QFormLayout(video_settings)
        self.video_length_spin = QtWidgets.QSpinBox()
        self.video_length_spin.setRange(1, 24 * 60 * 60)
        self.video_length_spin.setValue(self.video_length_seconds)
        self.fps_spin = QtWidgets.QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(self.camera_fps)
        video_layout.addRow("Length (sec)", self.video_length_spin)
        video_layout.addRow("FrameRate (fps)", self.fps_spin)
        self.settings_stack.addWidget(video_settings)

        left_layout.addWidget(self.settings_stack)

        path_group = QtWidgets.QGroupBox("Save Path")
        path_layout = QtWidgets.QFormLayout(path_group)
        path_layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        path_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setFixedWidth(self.mode_tab_width)
        self.path_btn = QtWidgets.QPushButton("Browse")
        path_row = QtWidgets.QHBoxLayout()
        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.path_btn)
        path_row.addStretch()
        path_layout.addRow("Path", path_row)

        left_layout.addWidget(path_group)

        self.start_btn.clicked.connect(self.handle_start_action)
        self.stop_btn.clicked.connect(self.stop_camera)
        self.preview_btn.clicked.connect(self.start_camera)
        self.update_btn.clicked.connect(self.request_update)
        self.path_btn.clicked.connect(self.choose_save_path)
        self.mode_tabs.currentChanged.connect(self.update_path_edit)
        self.mode_tabs.currentChanged.connect(self.update_settings_stack)
        self.update_path_edit()
        self.update_settings_stack()
        self.video_length_spin.valueChanged.connect(self.apply_video_settings)
        self.fps_spin.valueChanged.connect(self.apply_video_settings)
        self.image_interval_spin.valueChanged.connect(self.apply_image_settings)

    def _setup_timer(self) -> None:
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_frame)

    def start_camera(self) -> None:
        if self.is_running:
            return
        self._sync_save_paths()
        if Picamera2 is None:
            QtWidgets.QMessageBox.critical(
                self,
                "Camera Error",
                "picamera2 が見つかりません。Raspberry Pi OS で picamera2 をインストールしてください。",
            )
            return
        info_list = self._camera_info_list()
        info_text = self._camera_info_text(info_list)
        if info_text:
            self.status_label.setText(info_text)
        self._ensure_save_dirs()
        with self.camera_lock:
            self.cameras.clear()
            for cam_id in self.camera_ids:
                try:
                    internal_id = self._internal_camera_id(cam_id)
                    if internal_id >= len(info_list):
                        raise RuntimeError(
                            f"Camera {cam_id} は未検出です (内部ID {internal_id})"
                        )
                    cam = Picamera2(internal_id)
                    config = cam.create_video_configuration(
                        main={"size": (1800, 1080), "format": "RGB888"},
                        controls={"FrameRate": self.camera_fps},
                    )
                    cam.configure(config)
                    cam.start()
                    self.cameras[cam_id] = cam
                except Exception as exc:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Camera Error",
                        f"Camera {cam_id} を開けませんでした: {exc}\n{self._camera_info_text(info_list)}",
                    )

        if not self.cameras:
            return

        self.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Running")
        self.timer.start(self.frame_interval_ms)

    def stop_camera(self) -> None:
        self.stop_recording()
        self.stop_image_capture()
        self.is_running = False
        with self.camera_lock:
            cams = list(self.cameras.values())
            self.cameras.clear()
        for cam in cams:
            cam.stop()
            cam.close()
        self.timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Stopped")

    def _camera_info_list(self) -> list[dict]:
        if Picamera2 is None:
            return []
        try:
            return Picamera2.global_camera_info()
        except Exception:
            return []

    def _camera_info_text(self, info_list: list[dict]) -> str:
        if not info_list:
            return "No cameras detected."
        lines = ["Detected cameras:"]
        for idx, info in enumerate(info_list):
            model = info.get("Model", "Unknown")
            location = info.get("Location", "Unknown")
            lines.append(f"- ID {idx}: {model} ({location})")
        lines.append("Note: Picamera2 camera IDs are 0-based.")
        lines.append("Mapping: Camera 1 -> ID 0, Camera 2 -> ID 1")
        return "\n".join(lines)

    def _internal_camera_id(self, cam_id: int) -> int:
        return cam_id - 1

    def handle_start_action(self) -> None:
        mode_index = self.mode_tabs.currentIndex()
        if mode_index == 0:
            if not self.is_running:
                self.start_camera()
            self.toggle_image_capture()
            return

        if not self.is_running:
            self.start_camera()
        self.toggle_recording()

    def apply_video_settings(self) -> None:
        self.video_length_seconds = int(self.video_length_spin.value())
        self.camera_fps = int(self.fps_spin.value())
        if self.is_running:
            was_recording = self.recording
            if was_recording:
                self.stop_recording()
            self.stop_camera()
            self.start_camera()
            if was_recording:
                self.toggle_recording()

    def apply_image_settings(self) -> None:
        self.image_interval_seconds = int(self.image_interval_spin.value())
        if self.image_capturing:
            self.image_timer.start(self.image_interval_seconds * 1000)

    def request_update(self) -> None:
        if self.recording or self.image_capturing:
            QtWidgets.QMessageBox.warning(
                self,
                "Update",
                "撮影中は更新できません。停止してから更新してください。",
            )
            return
        if dbus is None:
            QtWidgets.QMessageBox.critical(
                self,
                "Update",
                "dbus が利用できません。python3-dbus をインストールしてください。",
            )
            return
        try:
            bus = dbus.SystemBus()
            proxy = bus.get_object("com.kaiko.Updater", "/com/kaiko/Updater")
            iface = dbus.Interface(proxy, "com.kaiko.Updater")
            success, message = iface.InstallUpdate()
            if success:
                QtWidgets.QMessageBox.information(self, "Update", message)
            else:
                QtWidgets.QMessageBox.warning(self, "Update", message)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Update",
                f"更新に失敗しました: {exc}",
            )

    def update_frame(self) -> None:
        if not self.is_running or not self.cameras:
            return

        with self.camera_lock:
            cams = list(self.cameras.items())
        for cam_id, cam in cams:
            try:
                frame = cam.capture_array()
            except Exception:
                self.status_label.setText(f"Frame read failed (Camera {cam_id})")
                continue
            self.frames[cam_id] = frame
            self._render_camera(cam_id, frame)

    def _render_camera(self, cam_id: int, frame) -> None:
        label = self.video_labels[cam_id]
        display_w = max(1, label.width())
        display_h = max(1, label.height())
        display = cv2.resize(frame, (display_w, display_h))

        h, w, _ = display.shape
        q_image = QtGui.QImage(display.data, w, h, w * 3, QtGui.QImage.Format.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(q_image)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor("lime"))
        pen.setWidth(2)
        painter.setPen(pen)

        painter.end()

        self.video_labels[cam_id].setPixmap(pixmap)

    def capture_now(self) -> None:
        if not self.frames:
            return
        self._sync_save_paths()
        self._ensure_save_dirs()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for cam_id, frame in self.frames.items():
            filename = f"{self.exp_name}_{timestamp}_cam{cam_id}.jpg"
            filepath = self.save_path / filename
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(filepath), bgr)
        QtWidgets.QMessageBox.information(
            self,
            "Captured",
            f"Saved {len(self.frames)} image(s) to {self.save_path}.",
        )

    def toggle_image_capture(self) -> None:
        if self.image_capturing:
            self.stop_image_capture()
            return
        if not self.is_running:
            return
        self.image_capturing = True
        self.image_timer.start(self.image_interval_seconds * 1000)
        self._capture_image_tick()

    def stop_image_capture(self) -> None:
        if not self.image_capturing:
            return
        self.image_capturing = False
        self.image_timer.stop()

    def _capture_image_tick(self) -> None:
        if not self.image_capturing:
            return
        self.capture_now()

    def toggle_recording(self) -> None:
        if self.recording:
            self.stop_recording()
            return
        if not self.cameras:
            QtWidgets.QMessageBox.warning(self, "Recording", "カメラを開始してから録画してください。")
            return
        if H264Encoder is None:
            QtWidgets.QMessageBox.critical(
                self,
                "Recording Error",
                "H264Encoder が利用できません。picamera2 のエンコーダが必要です。",
            )
            return
        if self.record_thread and self.record_thread.is_alive():
            return
        self._sync_save_paths()
        self._ensure_save_dirs()
        self.recording = True
        self.record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.record_thread.start()

    def stop_recording(self) -> None:
        if not self.recording:
            return
        self.recording = False
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=2)

    def _record_loop(self) -> None:
        if H264Encoder is None:
            return
        while self.recording:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            with self.camera_lock:
                cams = list(self.cameras.items())
            if not cams:
                break
            for cam_id, cam in cams:
                filename = f"{timestamp}_cam{cam_id}.h264"
                filepath = self.video_save_path / filename
                encoder = H264Encoder()
                try:
                    cam.start_recording(encoder, str(filepath))
                except Exception:
                    self.recording = False
                    break

            start_time = time.time()
            while self.recording and time.time() - start_time < self.video_length_seconds:
                time.sleep(0.2)

            with self.camera_lock:
                cams = list(self.cameras.items())
            for cam_id, cam in cams:
                try:
                    cam.stop_recording()
                except Exception:
                    pass

            if not self.recording:
                break
            time.sleep(self.video_interval_seconds)

    def choose_save_path(self) -> None:
        self._sync_save_paths()
        current = str(self._current_mode_path())
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Save Path", current)
        if not selected:
            return
        self.path_edit.setText(selected)
        self._sync_save_paths()
        self._ensure_save_dirs()

    def _sync_save_paths(self) -> None:
        mode_path = Path(self.path_edit.text()).expanduser()
        if self._is_image_mode():
            self.save_path = mode_path
        else:
            self.video_save_path = mode_path

    def update_path_edit(self) -> None:
        self.path_edit.setText(str(self._current_mode_path()))
        self.path_edit.setFixedWidth(self.mode_tab_width)

    def update_settings_stack(self) -> None:
        self.settings_stack.setCurrentIndex(self.mode_tabs.currentIndex())

    def _current_mode_path(self) -> Path:
        return self.save_path if self._is_image_mode() else self.video_save_path

    def _is_image_mode(self) -> bool:
        return self.mode_tabs.currentIndex() == 0

    def _ensure_save_dirs(self) -> None:
        self.save_path.mkdir(parents=True, exist_ok=True)
        self.video_save_path.mkdir(parents=True, exist_ok=True)


    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.stop_camera()
        event.accept()


def main() -> None:
    app = QtWidgets.QApplication([])
    window = CameraRoiApp()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()

