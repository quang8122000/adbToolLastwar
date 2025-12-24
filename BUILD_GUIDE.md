# Last War Monitor - Build Instructions

## 📱 Chạy GUI version (không cần build)

```bash
python3 monitor_game_gui.py
```

## 🔨 Build thành macOS App

### Bước 1: Cài đặt PyInstaller

```bash
pip3 install pyinstaller pillow pytesseract
```

### Bước 2: Build app

```bash
chmod +x build_app.sh
./build_app.sh
```

### Bước 3: Chạy app

```bash
open dist/LastWarMonitor.app
```

### Bước 4: Copy vào Applications (tùy chọn)

```bash
cp -r dist/LastWarMonitor.app /Applications/
```

## 📝 Features của GUI version

- ✅ **Giao diện đẹp**: Tkinter GUI với theme dark
- ✅ **Log realtime**: Tất cả log hiển thị trên GUI
- ✅ **Config dễ dàng**: Thay đổi package, target texts, interval
- ✅ **Start/Stop button**: Điều khiển monitor dễ dàng
- ✅ **Auto-scroll log**: Log tự động cuộn xuống
- ✅ **Clear log**: Nút xóa log
- ✅ **Status indicator**: Hiển thị trạng thái running/stopped

## 🎨 Tùy chỉnh

Để thay đổi icon app, tạo file `app_icon.icns` hoặc xóa dòng `--icon=app_icon.icns` trong `build_app.sh`.

## 🚀 Build nhanh với PyInstaller CLI

```bash
pyinstaller --name="LastWarMonitor" --windowed --onefile monitor_game_gui.py
```

## 📦 Các file cần thiết

- `monitor_game.py` - Core logic (backend)
- `monitor_game_gui.py` - GUI version (frontend)
- `build_app.sh` - Build script
- `requirements.txt` - Dependencies

## ⚠️ Lưu ý

- App cần **ADB** đã được cài đặt và trong PATH
- Cần **Tesseract** cho OCR: `brew install tesseract`
- Thiết bị Android phải được kết nối qua USB với USB debugging enabled
