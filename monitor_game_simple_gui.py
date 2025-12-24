#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI version đơn giản - Chỉ nhận diện text và thông báo liên tục
"""

import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import sys
import subprocess
import time
import os
from datetime import datetime

try:
    from PIL import Image
    import pytesseract

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class SimpleTextMonitor:
    """Monitor đơn giản chỉ nhận diện text và thông báo"""

    def __init__(self, package_name, target_texts, ocr_region=None, debug=False):
        self.package_name = package_name
        self.target_texts = (
            target_texts if isinstance(target_texts, list) else [target_texts]
        )
        self.ocr_region = ocr_region
        self.debug = debug
        self.stop_requested = False
        self.cached_screenshot = None

    def run_adb_command(self, command):
        """Chạy lệnh ADB và trả về kết quả"""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, encoding="utf-8"
            )
            return result.stdout
        except Exception as e:
            print(f"Lỗi khi chạy lệnh ADB: {e}")
            return ""

    def check_device_connected(self):
        """Kiểm tra xem có thiết bị Android nào được kết nối không"""
        output = self.run_adb_command("adb devices")
        lines = output.strip().split("\n")
        if len(lines) > 1:
            devices = [line for line in lines[1:] if line.strip() and "device" in line]
            return len(devices) > 0
        return False

    def check_app_running(self):
        """Kiểm tra xem ứng dụng có đang chạy không"""
        output = self.run_adb_command(f"adb shell pidof {self.package_name}")
        return output.strip() != ""

    def get_screen_content_ocr(self):
        """Lấy screenshot và nhận dạng text bằng OCR"""
        # Chụp screenshot và lưu vào thiết bị
        self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")

        # Pull screenshot về máy
        self.run_adb_command(
            "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
        )

        # Mở ảnh và chạy OCR
        try:
            img = Image.open("/tmp/screenshot.png")
            width, height = img.size

            self.cached_screenshot = img

            # Crop vùng cần OCR nếu có chỉ định
            if self.ocr_region:
                top_percent, bottom_percent = self.ocr_region
                crop_top = int(height * top_percent)
                crop_bottom = int(height * bottom_percent)
                img_crop = img.crop((0, crop_top, width, crop_bottom))
                if self.debug:
                    print(f"[DEBUG] Crop vùng OCR: y={crop_top} đến y={crop_bottom}")
            else:
                img_crop = img

            # Resize 50% để cân bằng tốc độ và độ chính xác
            crop_width, crop_height = img_crop.size
            img_resized = img_crop.resize(
                (crop_width // 2, crop_height // 2), Image.Resampling.LANCZOS
            )

            # Nhận dạng text từ ảnh
            text = pytesseract.image_to_string(img_resized, lang="eng")

            if self.debug:
                print(f"\n[DEBUG] OCR detected text:\n{text[:500]}...\n")

            return text
        except Exception as e:
            print(f"⚠️  Lỗi khi OCR: {e}")
            self.cached_screenshot = None
            return ""

    def search_text_in_screen(self):
        """Tìm kiếm text trong màn hình hiện tại"""
        content = self.get_screen_content_ocr()

        # Tìm kiếm tất cả các target texts
        for target in self.target_texts:
            if target in content:
                return target

        return None

    def send_notification(self, found_text):
        """Gửi thông báo khi tìm thấy text"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"\n{'='*50}\n⚠️  THÔNG BÁO: Đã tìm thấy '{found_text}'!\n⏰  Thời gian: {timestamp}\n{'='*50}\n"
        print(message)

        # Phát âm thanh thông báo (macOS)
        os.system("afplay /System/Library/Sounds/Glass.aiff &")

        # Gửi notification trên macOS
        os.system(
            f"""osascript -e 'display notification "Đã tìm thấy: {found_text}" with title "⚠️ Game Monitor" sound name "Glass"' &"""
        )

    def stop(self):
        """Yêu cầu dừng monitor"""
        self.stop_requested = True

    def monitor(self, interval=2, notification_interval=3):
        """Theo dõi liên tục và thông báo liên tục khi tìm thấy"""
        print(f"🎮 Bắt đầu theo dõi game: {self.package_name}")
        print(f"🔍 Tìm kiếm text: {self.target_texts}")
        print(f"⏱️  Kiểm tra mỗi {interval} giây")
        print(f"🔔 Thông báo mỗi {notification_interval} giây khi tìm thấy")
        if self.debug:
            print(f"🐛 Debug mode: BẬT")
        print(f"{'='*50}\n")

        # Kiểm tra kết nối thiết bị
        if not self.check_device_connected():
            print(
                "❌ Không tìm thấy thiết bị Android. Vui lòng kết nối thiết bị và bật USB debugging."
            )
            return

        print("✅ Đã kết nối thiết bị Android")

        check_count = 0
        found_text = None
        last_notification_time = 0

        try:
            while not self.stop_requested:
                check_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S")

                # Kiểm tra app có đang chạy không
                if not self.check_app_running():
                    print(f"[{timestamp}] ⏸️  App chưa chạy. Chờ app khởi động...")
                    found_text = None  # Reset khi app không chạy
                    time.sleep(interval)
                    continue

                print(f"[{timestamp}] 🔍 Kiểm tra lần #{check_count}...", end=" ")

                # Tìm kiếm text
                result = self.search_text_in_screen()

                if result:
                    print(f"✅ Tìm thấy '{result}'!")
                    found_text = result

                    # Thông báo liên tục theo interval
                    current_time = time.time()
                    if current_time - last_notification_time >= notification_interval:
                        self.send_notification(found_text)
                        last_notification_time = current_time

                else:
                    print("❌ Chưa tìm thấy")
                    found_text = None

                time.sleep(interval)

            if self.stop_requested:
                print("\n🛑 Đã nhận lệnh dừng từ GUI.")

        except KeyboardInterrupt:
            print("\n\n🛑 Đã dừng theo dõi bởi người dùng.")
        except Exception as e:
            print(f"\n❌ Lỗi: {e}")


class SimpleMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎮 Simple Text Monitor")
        self.root.geometry("850x650")
        self.root.minsize(650, 450)

        self.monitor = None
        self.monitor_thread = None
        self.is_running = False

        self.setup_ui()

    def setup_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="🎮 Simple Text Monitor",
            font=("SF Pro Display", 18, "bold"),
            bg="#2c3e50",
            fg="white",
        )
        title_label.pack(pady=15)

        # Config Frame
        config_frame = tk.LabelFrame(
            self.root, text="⚙️ Cấu hình", font=("SF Pro", 12, "bold")
        )
        config_frame.pack(fill=tk.X, padx=10, pady=10)

        # Package name
        tk.Label(config_frame, text="Package Name:", font=("SF Pro", 10)).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.package_entry = tk.Entry(config_frame, width=40, font=("SF Mono", 10))
        self.package_entry.insert(0, "com.fun.lastwar.vn.gp")
        self.package_entry.grid(row=0, column=1, padx=10, pady=5)

        # Target texts
        tk.Label(config_frame, text="Target Texts:", font=("SF Pro", 10)).grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.target_entry = tk.Entry(config_frame, width=40, font=("SF Mono", 10))
        self.target_entry.insert(0, "Dig Up Treasure, Test Flight Failure")
        self.target_entry.grid(row=1, column=1, padx=10, pady=5)

        # Check interval
        tk.Label(config_frame, text="Check Interval (s):", font=("SF Pro", 10)).grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.interval_entry = tk.Entry(config_frame, width=10, font=("SF Mono", 10))
        self.interval_entry.insert(0, "2")
        self.interval_entry.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        # Notification interval
        tk.Label(
            config_frame, text="Notification Interval (s):", font=("SF Pro", 10)
        ).grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        self.notification_interval_entry = tk.Entry(
            config_frame, width=10, font=("SF Mono", 10)
        )
        self.notification_interval_entry.insert(0, "3")
        self.notification_interval_entry.grid(
            row=3, column=1, sticky=tk.W, padx=10, pady=5
        )

        # Options
        options_frame = tk.LabelFrame(
            self.root, text="🎛️ Tùy chọn", font=("SF Pro", 12, "bold")
        )
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        self.debug_var = tk.BooleanVar(value=False)

        tk.Checkbutton(
            options_frame,
            text="Debug mode",
            variable=self.debug_var,
            font=("SF Pro", 10),
        ).pack(anchor=tk.W, padx=10, pady=2)

        # Control buttons
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_btn = tk.Button(
            control_frame,
            text="▶️  Start Monitor",
            command=self.start_monitor,
            bg="#27ae60",
            fg="white",
            font=("SF Pro", 12, "bold"),
            width=15,
            height=2,
            relief=tk.RAISED,
            cursor="hand2",
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(
            control_frame,
            text="⏹️  Stop Monitor",
            command=self.stop_monitor,
            bg="#e74c3c",
            fg="white",
            font=("SF Pro", 12, "bold"),
            width=15,
            height=2,
            relief=tk.RAISED,
            state=tk.DISABLED,
            cursor="hand2",
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = tk.Button(
            control_frame,
            text="🗑️  Clear Log",
            command=self.clear_log,
            bg="#95a5a6",
            fg="white",
            font=("SF Pro", 12, "bold"),
            width=15,
            height=2,
            relief=tk.RAISED,
            cursor="hand2",
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        # Status
        status_frame = tk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10)

        self.status_label = tk.Label(
            status_frame, text="⏸️  Đang chờ...", font=("SF Pro", 11), fg="#7f8c8d"
        )
        self.status_label.pack(anchor=tk.W)

        # Log area
        log_frame = tk.LabelFrame(self.root, text="📝 Log", font=("SF Pro", 12, "bold"))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("SF Mono", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            relief=tk.FLAT,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Redirect stdout to log
        sys.stdout = TextRedirector(self.log_text, "stdout")

        # Initial log
        self.log("✅ Simple Monitor GUI đã sẵn sàng!")
        self.log("📱 Hãy đảm bảo thiết bị Android đã kết nối qua ADB")
        self.log("🔔 Chương trình sẽ thông báo liên tục khi tìm thấy text\n")

    def log(self, message):
        """Log message to text area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def clear_log(self):
        """Clear log text"""
        self.log_text.delete(1.0, tk.END)
        self.log("🗑️  Log đã được xóa\n")

    def start_monitor(self):
        """Start monitoring"""
        if self.is_running:
            return

        # Get config
        package = self.package_entry.get().strip()
        target_texts = [t.strip() for t in self.target_entry.get().split(",")]
        interval = float(self.interval_entry.get())
        notification_interval = float(self.notification_interval_entry.get())
        debug = self.debug_var.get()

        if not package or not target_texts:
            self.log("❌ Vui lòng điền đầy đủ thông tin!\n")
            return

        # Disable controls
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.package_entry.config(state=tk.DISABLED)
        self.target_entry.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.DISABLED)
        self.notification_interval_entry.config(state=tk.DISABLED)

        self.is_running = True
        self.status_label.config(text="▶️  Đang chạy...", fg="#27ae60")

        # Create monitor instance
        self.monitor = SimpleTextMonitor(
            package,
            target_texts,
            ocr_region=(0.7, 1.0),  # Chỉ OCR 30% phần dưới màn hình
            debug=debug,
        )

        # Start in thread
        self.monitor_thread = threading.Thread(
            target=self.run_monitor, args=(interval, notification_interval), daemon=True
        )
        self.monitor_thread.start()

    def run_monitor(self, interval, notification_interval):
        """Run monitor in thread"""
        try:
            self.monitor.monitor(
                interval=interval, notification_interval=notification_interval
            )
        except Exception as e:
            self.log(f"\n❌ Lỗi: {e}\n")
        finally:
            self.is_running = False
            self.root.after(0, self.reset_controls)

    def stop_monitor(self):
        """Stop monitoring"""
        if self.monitor and self.is_running:
            self.log("\n🛑 Đang gửi lệnh dừng...\n")
            self.monitor.stop()
            self.is_running = False
            self.status_label.config(text="⏹️  Đã dừng", fg="#e74c3c")

    def reset_controls(self):
        """Reset control buttons"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.package_entry.config(state=tk.NORMAL)
        self.target_entry.config(state=tk.NORMAL)
        self.interval_entry.config(state=tk.NORMAL)
        self.notification_interval_entry.config(state=tk.NORMAL)
        self.status_label.config(text="⏸️  Đang chờ...", fg="#7f8c8d")


class TextRedirector:
    """Redirect stdout to text widget"""

    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, message):
        self.widget.insert(tk.END, message)
        self.widget.see(tk.END)

    def flush(self):
        pass


def main():
    if not OCR_AVAILABLE:
        print("⚠️  Cần cài đặt thư viện OCR:")
        print("   brew install tesseract")
        print("   pip3 install Pillow pytesseract")
        return

    root = tk.Tk()
    app = SimpleMonitorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
