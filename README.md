# Game Monitor Tool - Công cụ theo dõi Game

Script Python để theo dõi game Last War và thông báo khi xuất hiện chữ "Đào Kho Báu".

## Yêu cầu

1. **ADB (Android Debug Bridge)** đã được cài đặt
2. **Python 3** đã được cài đặt
3. Thiết bị Android với USB Debugging được bật
4. Game "com.fun.lastwar.vn.gp" đã được cài đặt trên thiết bị

## Cài đặt ADB (nếu chưa có)

### macOS:

```bash
brew install android-platform-tools
```

### Kiểm tra ADB đã cài đặt:

```bash
adb version
```

## Hướng dẫn sử dụng

### 1. Kết nối thiết bị Android

- Kết nối thiết bị Android qua USB
- Bật USB Debugging trên thiết bị:
  - Vào **Cài đặt** → **Về điện thoại** → Nhấn 7 lần vào **Số bản dựng** để bật chế độ Developer
  - Vào **Cài đặt** → **Tùy chọn nhà phát triển** → Bật **USB Debugging**

### 2. Kiểm tra kết nối

```bash
adb devices
```

Bạn sẽ thấy thiết bị của mình trong danh sách. Lần đầu tiên cần chấp nhận yêu cầu debug trên điện thoại.

### 3. Chạy script

```bash
python3 monitor_game.py
```

hoặc:

```bash
chmod +x monitor_game.py
./monitor_game.py
```

## Cách hoạt động

Script sẽ:

1. Kiểm tra kết nối thiết bị Android
2. Kiểm tra game có đang chạy không
3. Định kỳ dump UI hierarchy từ màn hình (mặc định 5 giây/lần)
4. Tìm kiếm text "Đào Kho Báu" trong nội dung màn hình
5. Khi tìm thấy:
   - Hiển thị thông báo trên terminal
   - Phát âm thanh cảnh báo
   - Hiển thị notification trên macOS
   - Hỏi người dùng có muốn tiếp tục theo dõi không

## Tùy chỉnh

Bạn có thể thay đổi các tham số trong file `monitor_game.py`:

```python
PACKAGE_NAME = "com.fun.lastwar.vn.gp"  # Tên package game
TARGET_TEXT = "Đào Kho Báu"              # Text cần tìm
CHECK_INTERVAL = 5                       # Thời gian giữa các lần kiểm tra (giây)
```

## Dừng chương trình

Nhấn `Ctrl + C` để dừng script bất cứ lúc nào.

## Lưu ý

- Script yêu cầu quyền truy cập vào thiết bị Android qua ADB
- Kiểm tra quá thường xuyên có thể ảnh hưởng đến hiệu năng thiết bị
- Đảm bảo game đang chạy trước khi script bắt đầu theo dõi
- Notification chỉ hoạt động trên macOS

## Troubleshooting

### Không tìm thấy thiết bị:

```bash
adb kill-server
adb start-server
adb devices
```

### Lỗi permission denied:

```bash
adb kill-server
sudo adb start-server
```

### Không tìm thấy text:

- Đảm bảo game đang hiển thị màn hình có chứa text
- Thử thay đổi `TARGET_TEXT` thành một phần của text đó
