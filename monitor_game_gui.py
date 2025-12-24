#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI version - Game Monitor cho Last War
"""

import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import sys
import json
import os
from monitor_game import GameMonitor
from datetime import datetime

try:
    from PIL import Image, ImageTk, ImageDraw

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class GameMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎮 Last War Monitor")
        self.root.geometry("900x800")
        self.root.minsize(700, 600)

        self.monitor = None
        self.monitor_thread = None
        self.is_running = False

        # Config file
        self.config_file = os.path.expanduser("~/.lastwar_monitor_config.json")

        # Preview window
        self.preview_window = None
        self.preview_canvas = None

        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="🎮 Last War Auto Monitor",
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

        # OCR Region config
        ocr_frame = tk.LabelFrame(
            self.root, text="📦 OCR Region (hỗ trợ %, px)", font=("SF Pro", 12, "bold")
        )
        ocr_frame.pack(fill=tk.X, padx=10, pady=5)

        # Row 1: Top, Left
        tk.Label(ocr_frame, text="Top:", font=("SF Pro", 10)).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.top_entry = tk.Entry(ocr_frame, width=10, font=("SF Mono", 10))
        self.top_entry.insert(0, "70%")
        self.top_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(ocr_frame, text="Left:", font=("SF Pro", 10)).grid(
            row=0, column=2, sticky=tk.W, padx=10, pady=5
        )
        self.left_entry = tk.Entry(ocr_frame, width=10, font=("SF Mono", 10))
        self.left_entry.insert(0, "0")
        self.left_entry.grid(row=0, column=3, padx=5, pady=5)

        # Row 2: Width, Height
        tk.Label(ocr_frame, text="Width:", font=("SF Pro", 10)).grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.width_entry = tk.Entry(ocr_frame, width=10, font=("SF Mono", 10))
        self.width_entry.insert(0, "100%")
        self.width_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(ocr_frame, text="Height:", font=("SF Pro", 10)).grid(
            row=1, column=2, sticky=tk.W, padx=10, pady=5
        )
        self.height_entry = tk.Entry(ocr_frame, width=10, font=("SF Mono", 10))
        self.height_entry.insert(0, "30%")
        self.height_entry.grid(row=1, column=3, padx=5, pady=5)

        # Preview button
        self.preview_btn = tk.Button(
            ocr_frame,
            text="👁️ Preview Region",
            command=self.preview_region,
            bg="#3498db",
            fg="white",
            font=("SF Pro", 10, "bold"),
            relief=tk.RAISED,
            cursor="hand2",
        )
        self.preview_btn.grid(row=0, column=4, rowspan=2, padx=10, pady=5)

        # Options
        options_frame = tk.LabelFrame(
            self.root, text="🎛️ Tùy chọn", font=("SF Pro", 12, "bold")
        )
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        self.auto_click_var = tk.BooleanVar(value=True)
        self.debug_var = tk.BooleanVar(value=False)

        tk.Checkbutton(
            options_frame,
            text="Auto-click",
            variable=self.auto_click_var,
            font=("SF Pro", 10),
        ).pack(anchor=tk.W, padx=10, pady=2)
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
        self.log("✅ GUI đã sẵn sàng!")
        self.log("📱 Hãy đảm bảo thiết bị Android đã kết nối qua ADB\n")

    def log(self, message):
        """Log message to text area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def save_config(self):
        """Lưu config vào file JSON"""
        config = {
            "package_name": self.package_entry.get(),
            "target_texts": self.target_entry.get(),
            "check_interval": self.interval_entry.get(),
            "auto_click": self.auto_click_var.get(),
            "debug": self.debug_var.get(),
            "ocr_region": {
                "top": self.top_entry.get(),
                "left": self.left_entry.get(),
                "width": self.width_entry.get(),
                "height": self.height_entry.get(),
            },
        }
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
            if self.is_running:
                self.log("💾 Config đã được lưu")
        except Exception as e:
            self.log(f"⚠️  Lỗi khi lưu config: {e}")

    def load_config(self):
        """Load config từ file JSON"""
        if not os.path.exists(self.config_file):
            return

        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)

            # Load vào UI
            if "package_name" in config:
                self.package_entry.delete(0, tk.END)
                self.package_entry.insert(0, config["package_name"])

            if "target_texts" in config:
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, config["target_texts"])

            if "check_interval" in config:
                self.interval_entry.delete(0, tk.END)
                self.interval_entry.insert(0, config["check_interval"])

            if "auto_click" in config:
                self.auto_click_var.set(config["auto_click"])

            if "debug" in config:
                self.debug_var.set(config["debug"])

            if "ocr_region" in config:
                region = config["ocr_region"]
                self.top_entry.delete(0, tk.END)
                self.top_entry.insert(0, region.get("top", "70%"))

                self.left_entry.delete(0, tk.END)
                self.left_entry.insert(0, region.get("left", "0"))

                self.width_entry.delete(0, tk.END)
                self.width_entry.insert(0, region.get("width", "100%"))

                self.height_entry.delete(0, tk.END)
                self.height_entry.insert(0, region.get("height", "30%"))

            self.log("✅ Đã load config từ lần chạy trước")
        except Exception as e:
            self.log(f"⚠️  Lỗi khi load config: {e}")

    def clear_log(self):
        """Clear log text"""
        self.log_text.delete(1.0, tk.END)
        self.log("🗑️  Log đã được xóa\n")

    def preview_region(self):
        """Hiển thị preview vùng OCR trên screenshot"""
        if not PIL_AVAILABLE:
            self.log("⚠️  Cần cài đặt Pillow: pip3 install Pillow")
            return

        try:
            # Chụp screenshot
            import subprocess

            subprocess.run(
                "adb shell screencap -p /sdcard/screenshot.png", shell=True, check=True
            )
            subprocess.run(
                "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null",
                shell=True,
                check=True,
            )

            # Load image
            img = Image.open("/tmp/screenshot.png")
            width, height = img.size

            # Parse OCR region
            from monitor_game import GameMonitor

            temp_monitor = GameMonitor("dummy", "dummy")

            top_val = self.top_entry.get().strip() or "0"
            left_val = self.left_entry.get().strip() or "0"
            width_val = self.width_entry.get().strip() or "100%"
            height_val = self.height_entry.get().strip() or "100%"

            top = temp_monitor.parse_dimension(top_val, height) or 0
            left = temp_monitor.parse_dimension(left_val, width) or 0
            ocr_width = temp_monitor.parse_dimension(width_val, width) or width
            ocr_height = temp_monitor.parse_dimension(height_val, height) or height

            right = min(left + ocr_width, width)
            bottom = min(top + ocr_height, height)

            # Vẽ overlay
            draw = ImageDraw.Draw(img, "RGBA")

            # Vẽ vùng chọn (màu xanh lá trong suốt)
            draw.rectangle(
                [left, top, right, bottom],
                fill=(0, 255, 0, 50),
                outline=(0, 255, 0, 255),
                width=3,
            )

            # Vẽ text thông tin
            info_text = f"Region: ({left},{top}) -> ({right},{bottom})\nSize: {right-left}x{bottom-top}px"
            draw.text((left + 10, top + 10), info_text, fill=(0, 255, 0, 255))

            # Hiển thị trong cửa sổ mới
            if self.preview_window:
                self.preview_window.destroy()

            self.preview_window = tk.Toplevel(self.root)
            self.preview_window.title("👁️ OCR Region Preview")

            # Scale ảnh xuống để hiển thị vừa màn hình
            scale = min(1.0, 800 / width, 600 / height)
            display_width = int(width * scale)
            display_height = int(height * scale)
            img_resized = img.resize(
                (display_width, display_height), Image.Resampling.LANCZOS
            )

            # Hiển thị
            photo = ImageTk.PhotoImage(img_resized)
            label = tk.Label(self.preview_window, image=photo)
            label.image = photo  # Keep reference
            label.pack()

            # Button đóng
            close_btn = tk.Button(
                self.preview_window,
                text="✖️ Đóng Preview",
                command=self.preview_window.destroy,
                bg="#e74c3c",
                fg="white",
                font=("SF Pro", 10, "bold"),
            )
            close_btn.pack(pady=10)

            self.log(f"✅ Preview region: ({left},{top}) -> ({right},{bottom})")

        except Exception as e:
            self.log(f"⚠️  Lỗi khi preview: {e}")

    def start_monitor(self):
        """Start monitoring"""
        if self.is_running:
            return

        # Get config
        package = self.package_entry.get().strip()
        target_texts = [t.strip() for t in self.target_entry.get().split(",")]
        interval = float(self.interval_entry.get())
        auto_click = self.auto_click_var.get()
        debug = self.debug_var.get()

        # OCR Region
        ocr_region = {
            "top": self.top_entry.get().strip() or "0",
            "left": self.left_entry.get().strip() or "0",
            "width": self.width_entry.get().strip() or "100%",
            "height": self.height_entry.get().strip() or "100%",
        }

        if not package or not target_texts:
            self.log("❌ Vui lòng điền đầy đủ thông tin!\n")
            return

        # Ẩn preview window nếu đang mở
        if self.preview_window:
            self.preview_window.destroy()
            self.preview_window = None

        # Disable controls
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.package_entry.config(state=tk.DISABLED)
        self.target_entry.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.DISABLED)
        self.preview_btn.config(state=tk.DISABLED)

        self.is_running = True
        self.status_label.config(text="▶️  Đang chạy...", fg="#27ae60")

        # Lưu config
        self.save_config()

        # Pixel patterns
        PIXEL_PATTERNS = {
            "step3": [
                {"coord": (550, 1136), "color": "#FFFFFF"},
                {"coord": (545, 1136), "color": "#F8FBF9"},
            ],
            "step4": [
                {"coord": (542, 1472), "color": "#10B1FB"},
                {"coord": (537, 1472), "color": "#10B2FC"},
            ],
            "step5": [
                {"coord": (514, 819), "color": "#94C03D"},
                {"coord": (509, 819), "color": "#A7F200"},
            ],
        }

        # Create monitor instance
        self.monitor = GameMonitor(
            package,
            target_texts,
            use_ocr=True,
            debug=debug,
            auto_click=auto_click,
            click_delay=0.2,
            skip_color_check=True,
            ocr_region=ocr_region,
            pixel_patterns=PIXEL_PATTERNS,
            pattern_tolerance=20,
            pattern_match_ratio=0.6,
        )

        # Start in thread
        self.monitor_thread = threading.Thread(
            target=self.run_monitor, args=(interval,), daemon=True
        )
        self.monitor_thread.start()

    def run_monitor(self, interval):
        """Run monitor in thread"""
        try:
            self.monitor.monitor(interval=interval)
        except Exception as e:
            self.log(f"\n❌ Lỗi: {e}\n")
        finally:
            self.is_running = False
            self.root.after(0, self.reset_controls)

    def stop_monitor(self):
        """Stop monitoring"""
        if self.monitor and self.is_running:
            self.log("\n🛑 Đang gửi lệnh dừng...\n")
            self.monitor.stop()  # Gọi stop() method
            self.is_running = False
            self.status_label.config(text="⏹️  Đã dừng", fg="#e74c3c")

    def reset_controls(self):
        """Reset control buttons"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.package_entry.config(state=tk.NORMAL)
        self.target_entry.config(state=tk.NORMAL)
        self.interval_entry.config(state=tk.NORMAL)
        self.preview_btn.config(state=tk.NORMAL)
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
    root = tk.Tk()
    app = GameMonitorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
