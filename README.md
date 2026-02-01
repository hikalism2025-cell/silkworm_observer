# Silkworm Observer

GUI app to preview a camera feed, draw ROIs, and assign names for experiments.

## Features
- Start/stop camera preview
- Draw ROI rectangles with the mouse
- Name each ROI
- Save/load ROI definitions to `rois.json`

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
python app.py
```

## Qt版（商品レベルのUI向け）
Tkinter版より柔軟にUIを作り込めるため、プロダクト用途ならQt版を推奨します。

```bash
python app_qt_v2.py
```

## Notes
- Default camera index is `0`. Update `camera_index` in `app.py` if needed.
- ROI coordinates are stored in original frame coordinates.
- Qt版は Raspberry Pi OS の `picamera2` を利用します。Pi上で `sudo apt install -y python3-picamera2` を実行してください。
- Qt版の保存先は `app_qt_v2.py` 内の `save_path` に設定しています。
- 更新はアプリ内の `Update` ボタンから実行します（撮影中は更新不可）。

## Releases / Updates
- Release運用と `latest.json` のルールは `RELEASE.md` を参照してください。
