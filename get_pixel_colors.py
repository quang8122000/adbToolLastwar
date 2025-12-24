#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tool để lấy màu pixel từ màn hình Android game
Dùng để cập nhật PIXEL_PATTERNS trong monitor_game.py
"""

import subprocess
from PIL import Image


def run_adb_command(command):
    """Chạy lệnh ADB"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return ""


def capture_screenshot():
    """Chụp screenshot từ thiết bị Android"""
    print("📸 Đang chụp screenshot từ thiết bị...")
    run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
    run_adb_command("adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null")

    try:
        img = Image.open("/tmp/screenshot.png")
        print(f"✅ Đã chụp screenshot: {img.size[0]}x{img.size[1]} pixels\n")
        return img
    except Exception as e:
        print(f"❌ Không thể mở screenshot: {e}")
        return None


def get_pixel_color(img, x, y):
    """Lấy màu pixel tại tọa độ (x, y)"""
    try:
        pixel = img.getpixel((x, y))
        color = "#{:02x}{:02x}{:02x}".format(pixel[0], pixel[1], pixel[2]).upper()
        return color
    except Exception as e:
        return f"ERROR: {e}"


def get_predefined_coords():
    """Trả về các tọa độ được định nghĩa sẵn"""
    return {
        "step3": [
            (550, 1136),  # Pixel chính
            (545, 1136),  # Trái
            (555, 1136),  # Phải
            (550, 1131),  # Trên
            (550, 1141),  # Dưới
        ],
        "step4": [
            (538, 1470),  # Pixel chính
            (533, 1470),  # Trái
            (543, 1470),  # Phải
            (538, 1465),  # Trên
            (538, 1475),  # Dưới
        ],
        "step5": [
            (514, 819),  # Pixel chính
            (509, 819),  # Trái
            (519, 819),  # Phải
            (514, 814),  # Trên
            (514, 824),  # Dưới
        ],
    }


def print_pattern_config(step_name, coords, colors):
    """In ra config pattern để copy vào monitor_game.py"""
    print(f"\n{'='*60}")
    print(f"📋 Copy đoạn này vào PIXEL_PATTERNS['{step_name}']:")
    print(f"{'='*60}")
    print(f"'{step_name}': [")
    for i, ((x, y), color) in enumerate(zip(coords, colors)):
        comment = ""
        if i == 0:
            comment = "  # Pixel chính"
        elif i == 1:
            comment = "  # Trái"
        elif i == 2:
            comment = "  # Phải"
        elif i == 3:
            comment = "  # Trên"
        elif i == 4:
            comment = "  # Dưới"

        print(f"    {{'coord': ({x}, {y}), 'color': '{color}'}},{comment}")
    print("],")
    print(f"{'='*60}\n")


def main():
    print("🎮 TOOL LẤY MÀU PIXEL TỪ GAME")
    print("=" * 60)

    # Kiểm tra kết nối ADB
    devices = run_adb_command("adb devices")
    if "device" not in devices or len(devices.strip().split("\n")) < 2:
        print("❌ Không tìm thấy thiết bị Android. Vui lòng kết nối thiết bị!")
        return

    print("✅ Đã kết nối thiết bị Android\n")

    # Menu
    print("Chọn chế độ:")
    print("  1. Lấy màu cho STEP 3 (tọa độ 550, 1136)")
    print("  2. Lấy màu cho STEP 4 (tọa độ 538, 1470)")
    print("  3. Lấy màu cho STEP 5 (tọa độ 514, 819)")
    print("  4. Lấy màu cả STEP 3, 4 và 5")
    print("  5. Nhập tọa độ thủ công")
    print()

    choice = input("👉 Chọn (1-5): ").strip()

    # Chụp screenshot
    img = capture_screenshot()
    if not img:
        return

    predefined = get_predefined_coords()

    if choice == "1":
        # Step 3
        coords = predefined["step3"]
        print("🔍 Lấy màu cho STEP 3:")
        print(f"{'Tọa độ':<20} {'Màu':<10}")
        print("-" * 30)

        colors = []
        for x, y in coords:
            color = get_pixel_color(img, x, y)
            colors.append(color)
            print(f"({x:4}, {y:4}){' '*8} {color}")

        print_pattern_config("step3", coords, colors)

    elif choice == "2":
        # Step 4
        coords = predefined["step4"]
        print("🔍 Lấy màu cho STEP 4:")
        print(f"{'Tọa độ':<20} {'Màu':<10}")
        print("-" * 30)

        colors = []
        for x, y in coords:
            color = get_pixel_color(img, x, y)
            colors.append(color)
            print(f"({x:4}, {y:4}){' '*8} {color}")

        print_pattern_config("step4", coords, colors)

    elif choice == "3":
        # Step 5
        coords = predefined["step5"]
        print("🔍 Lấy màu cho STEP 5:")
        print(f"{'Tọa độ':<20} {'Màu':<10}")
        print("-" * 30)

        colors = []
        for x, y in coords:
            color = get_pixel_color(img, x, y)
            colors.append(color)
            print(f"({x:4}, {y:4}){' '*8} {color}")

        print_pattern_config("step5", coords, colors)

    elif choice == "4":
        # Cả 3 steps
        for step_name in ["step3", "step4", "step5"]:
            coords = predefined[step_name]
            print(f"\n🔍 Lấy màu cho {step_name.upper()}:")
            print(f"{'Tọa độ':<20} {'Màu':<10}")
            print("-" * 30)

            colors = []
            for x, y in coords:
                color = get_pixel_color(img, x, y)
                colors.append(color)
                print(f"({x:4}, {y:4}){' '*8} {color}")

            print_pattern_config(step_name, coords, colors)

    elif choice == "5":
        # Manual input - nhập tọa độ chính và tự động tạo 5 điểm xung quanh
        print("\n📝 Nhập tọa độ chính (pixel trung tâm)")
        print("Ví dụ: 538,1470")
        print("Hệ thống sẽ tự động tạo 5 tọa độ: chính, trái, phải, trên, dưới")
        coords_input = input("👉 Tọa độ chính: ").strip()

        try:
            x, y = map(int, coords_input.split(","))
        except:
            print(f"❌ Tọa độ không hợp lệ! Vui lòng nhập theo format: x,y")
            return

        # Tạo 5 tọa độ: chính, trái, phải, trên, dưới
        offset = 5
        coords = [
            (x, y),  # Pixel chính
            (x - offset, y),  # Trái
            (x + offset, y),  # Phải
            (x, y - offset),  # Trên
            (x, y + offset),  # Dưới
        ]

        print(f"\n🔍 Lấy màu tại tọa độ chính ({x}, {y}) và 4 điểm xung quanh:")
        print(f"{'Tọa độ':<20} {'Màu':<10} {'Vị trí':<15}")
        print("-" * 50)

        colors = []
        positions = ["Pixel chính", "Trái (-5)", "Phải (+5)", "Trên (-5)", "Dưới (+5)"]
        for i, (px, py) in enumerate(coords):
            color = get_pixel_color(img, px, py)
            colors.append(color)
            print(f"({px:4}, {py:4}){' '*8} {color:<10} {positions[i]}")

        # Copy format
        print(f"\n{'='*60}")
        print("📋 Copy đoạn này vào PIXEL_PATTERNS:")
        print(f"{'='*60}")
        print("'custom': [")
        for i, ((px, py), color) in enumerate(zip(coords, colors)):
            comment = ""
            if i == 0:
                comment = "  # Pixel chính"
            elif i == 1:
                comment = "  # Trái"
            elif i == 2:
                comment = "  # Phải"
            elif i == 3:
                comment = "  # Trên"
            elif i == 4:
                comment = "  # Dưới"
            print(f"    {{'coord': ({px}, {py}), 'color': '{color}'}},{comment}")
        print("],")
        print(f"{'='*60}\n")

    else:
        print("❌ Lựa chọn không hợp lệ!")


if __name__ == "__main__":
    main()
