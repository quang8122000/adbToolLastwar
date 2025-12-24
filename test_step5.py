#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Tool cho STEP 5 - Kiểm tra pixel pattern và auto-click
Hiển thị vị trí tìm thấy và vị trí auto-click bằng cách vẽ điểm đỏ lên screenshot
"""

import subprocess
import time
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


class Step5Tester:
    def __init__(
        self, pixel_pattern, click_coords=(544, 876), tolerance=20, match_ratio=0.6
    ):
        """
        Args:
            pixel_pattern: List các dict chứa coord và color
            click_coords: Tọa độ để auto-click (x, y)
            tolerance: Độ sai lệch màu cho phép (0-255)
            match_ratio: Tỷ lệ pixel khớp tối thiểu (0.0-1.0)
        """
        self.pixel_pattern = pixel_pattern
        self.click_coords = click_coords
        self.tolerance = tolerance
        self.match_ratio = match_ratio
        self.cached_screenshot = None

    def run_adb_command(self, command):
        """Chạy lệnh ADB"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            return ""

    def capture_screenshot(self):
        """Chụp screenshot từ thiết bị Android"""
        print("📸 Đang chụp screenshot từ thiết bị...")
        self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
        self.run_adb_command(
            "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
        )

        try:
            img = Image.open("/tmp/screenshot.png")
            print(f"✅ Đã chụp screenshot: {img.size[0]}x{img.size[1]} pixels")
            self.cached_screenshot = img
            return img
        except Exception as e:
            print(f"❌ Không thể mở screenshot: {e}")
            return None

    def check_pixel_pattern(self, img=None):
        """
        Kiểm tra pixel pattern có khớp không

        Returns:
            (is_match, matched_pixels, total_pixels, details)
        """
        if img is None:
            img = self.cached_screenshot

        if not img:
            print("❌ Không có screenshot để kiểm tra!")
            return False, 0, 0, []

        matched_pixels = 0
        total_pixels = len(self.pixel_pattern)
        details = []

        print(f"\n🔍 Kiểm tra {total_pixels} pixel trong pattern...")
        print(
            f"{'Tọa độ':<15} {'Mong đợi':<12} {'Thực tế':<12} {'Diff':<8} {'Kết quả':<8}"
        )
        print("-" * 65)

        for pixel_info in self.pixel_pattern:
            x, y = pixel_info["coord"]
            expected_color = pixel_info["color"]

            try:
                # Lấy màu thực tế
                actual_pixel = img.getpixel((x, y))
                actual_color = "#{:02x}{:02x}{:02x}".format(
                    actual_pixel[0], actual_pixel[1], actual_pixel[2]
                ).upper()

                # Chuyển hex sang RGB để so sánh
                expected_r = int(expected_color[1:3], 16)
                expected_g = int(expected_color[3:5], 16)
                expected_b = int(expected_color[5:7], 16)

                # Tính độ sai khác
                diff = (
                    abs(actual_pixel[0] - expected_r)
                    + abs(actual_pixel[1] - expected_g)
                    + abs(actual_pixel[2] - expected_b)
                )

                is_match = diff <= self.tolerance * 3
                if is_match:
                    matched_pixels += 1
                    result = "✅ Khớp"
                else:
                    result = "❌ Sai"

                print(
                    f"({x:4}, {y:4})  {expected_color:<12} {actual_color:<12} {diff:<8} {result}"
                )

                details.append(
                    {
                        "coord": (x, y),
                        "expected": expected_color,
                        "actual": actual_color,
                        "diff": diff,
                        "match": is_match,
                    }
                )

            except Exception as e:
                print(f"({x:4}, {y:4})  ⚠️  Lỗi: {e}")
                details.append(
                    {
                        "coord": (x, y),
                        "expected": expected_color,
                        "actual": "ERROR",
                        "diff": 999,
                        "match": False,
                    }
                )

        # Tính tỷ lệ khớp
        current_ratio = matched_pixels / total_pixels
        is_pass = current_ratio >= self.match_ratio

        print("-" * 65)
        print(
            f"📊 Kết quả: {matched_pixels}/{total_pixels} pixels khớp ({current_ratio*100:.1f}%)"
        )
        print(f"🎯 Ngưỡng yêu cầu: {self.match_ratio*100:.1f}%")
        print(
            f"{'✅ PASS - Pattern khớp!' if is_pass else '❌ FAIL - Pattern không khớp!'}\n"
        )

        return is_pass, matched_pixels, total_pixels, details

    def draw_markers_on_screenshot(self, details, save_path="/tmp/step5_marked.png"):
        """
        Vẽ các điểm đánh dấu lên screenshot
        - Màu xanh: pixel khớp
        - Màu đỏ: pixel không khớp
        - Màu vàng: vị trí auto-click
        """
        if not self.cached_screenshot:
            print("❌ Không có screenshot để vẽ!")
            return None

        img = self.cached_screenshot.copy()
        draw = ImageDraw.Draw(img)

        # Vẽ các pixel pattern
        for detail in details:
            x, y = detail["coord"]
            color = "lime" if detail["match"] else "red"

            # Vẽ dấu X lớn
            size = 10
            draw.line([(x - size, y - size), (x + size, y + size)], fill=color, width=3)
            draw.line([(x - size, y + size), (x + size, y - size)], fill=color, width=3)

            # Vẽ circle
            radius = 15
            draw.ellipse(
                [(x - radius, y - radius), (x + radius, y + radius)],
                outline=color,
                width=2,
            )

        # Vẽ vị trí auto-click (màu vàng, lớn hơn)
        cx, cy = self.click_coords

        # Vẽ dấu + lớn
        size = 20
        draw.line([(cx - size, cy), (cx + size, cy)], fill="yellow", width=4)
        draw.line([(cx, cy - size), (cx, cy + size)], fill="yellow", width=4)

        # Vẽ circle lớn
        radius = 30
        draw.ellipse(
            [(cx - radius, cy - radius), (cx + radius, cy + radius)],
            outline="yellow",
            width=3,
        )

        # Vẽ text
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 24
            )
        except:
            font = ImageFont.load_default()

        draw.text(
            (cx + 40, cy - 10), f"Auto-click\n({cx}, {cy})", fill="yellow", font=font
        )

        # Lưu ảnh
        img.save(save_path)
        print(f"💾 Đã lưu screenshot có đánh dấu: {save_path}")
        return save_path

    def click_at_coordinates(self, x, y):
        """Click vào tọa độ trên màn hình"""
        cmd = f"adb shell input tap {x} {y}"
        self.run_adb_command(cmd)

    def auto_click_10s(self):
        """Auto-click liên tục trong 10 giây"""
        x, y = self.click_coords
        click_duration = 10  # 10 giây
        click_interval = 0.07  # 70 mili giây

        print(f"\n🎯 Bắt đầu auto-click tại ({x}, {y})...")
        print(f"⏱️  Thời lượng: {click_duration}s")
        print(f"⚡ Tốc độ: {click_interval*1000:.0f}ms/click")

        click_start_time = time.time()
        click_count = 0

        while time.time() - click_start_time < click_duration:
            self.click_at_coordinates(x, y)
            click_count += 1

            # Hiển thị tiến độ mỗi giây
            elapsed = time.time() - click_start_time
            if click_count % 14 == 0:  # ~14 clicks/giây
                remaining = click_duration - elapsed
                print(f"⏰ Đã click {click_count} lần | Còn {remaining:.1f}s...")

            time.sleep(click_interval)

        total_time = time.time() - click_start_time
        print(f"\n✅ Hoàn thành!")
        print(f"📊 Tổng cộng: {click_count} clicks trong {total_time:.2f}s")
        print(f"⚡ Tốc độ trung bình: {click_count/total_time:.1f} clicks/giây\n")

    def run_test(self, auto_click=True, draw_markers=True):
        """
        Chạy test đầy đủ

        Args:
            auto_click: Có auto-click 10s không
            draw_markers: Có vẽ markers lên screenshot không
        """
        print("=" * 70)
        print("🧪 TEST STEP 5 - PIXEL PATTERN & AUTO-CLICK")
        print("=" * 70)

        # Kiểm tra kết nối ADB
        devices = self.run_adb_command("adb devices")
        if "device" not in devices or len(devices.strip().split("\n")) < 2:
            print("❌ Không tìm thấy thiết bị Android. Vui lòng kết nối thiết bị!")
            return False

        print("✅ Đã kết nối thiết bị Android\n")

        # Chụp screenshot
        img = self.capture_screenshot()
        if not img:
            return False

        # Kiểm tra pixel pattern
        is_pass, matched, total, details = self.check_pixel_pattern(img)

        # Vẽ markers nếu được yêu cầu
        if draw_markers:
            marked_path = self.draw_markers_on_screenshot(details)
            if marked_path:
                print(f"👁️  Mở file để xem vị trí đã đánh dấu:")
                print(f"   open {marked_path}\n")

        # Auto-click nếu pattern khớp và được yêu cầu
        if is_pass and auto_click:
            print("🎉 Pattern khớp! Bắt đầu auto-click...")
            time.sleep(1)
            self.auto_click_10s()
        elif not is_pass:
            print("⚠️  Pattern không khớp, bỏ qua auto-click.")

        print("=" * 70)
        print(f"✅ Test hoàn thành - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 70)

        return is_pass


def main():
    print("🎮 TOOL TEST STEP 5\n")

    # Cấu hình pixel pattern cho step5
    # Bạn có thể thay đổi tọa độ và màu sắc tại đây
    PIXEL_PATTERN_STEP5 = [
        {"coord": (514, 819), "color": "#94C03D"},  # Pixel chính
        {"coord": (509, 819), "color": "#A7F200"},  # Trái
        {"coord": (519, 819), "color": "#8DBE2F"},  # Phải
        {"coord": (514, 814), "color": "#9BD344"},  # Trên
        {"coord": (514, 824), "color": "#8DBE30"},  # Dưới
    ]

    # Tọa độ auto-click
    CLICK_COORDS = (544, 876)

    # Cấu hình
    TOLERANCE = 20  # Độ sai lệch màu cho phép
    MATCH_RATIO = 0.6  # 60% pixels phải khớp

    print(f"⚙️  Cấu hình:")
    print(f"   - Pattern: {len(PIXEL_PATTERN_STEP5)} pixels")
    print(f"   - Click coords: {CLICK_COORDS}")
    print(f"   - Tolerance: {TOLERANCE}")
    print(f"   - Match ratio: {MATCH_RATIO*100:.0f}%")
    print()

    # Tùy chọn
    print("Chọn chế độ test:")
    print("  1. Chỉ kiểm tra pattern (không click)")
    print("  2. Kiểm tra pattern + auto-click 10s (nếu khớp)")
    print("  3. Auto-click ngay (bỏ qua kiểm tra pattern)")
    print()

    choice = input("👉 Chọn (1-3, Enter=2): ").strip() or "2"

    # Tạo tester
    tester = Step5Tester(
        pixel_pattern=PIXEL_PATTERN_STEP5,
        click_coords=CLICK_COORDS,
        tolerance=TOLERANCE,
        match_ratio=MATCH_RATIO,
    )

    print()

    if choice == "1":
        # Chỉ kiểm tra pattern
        tester.run_test(auto_click=False, draw_markers=True)

    elif choice == "2":
        # Kiểm tra + auto-click
        tester.run_test(auto_click=True, draw_markers=True)

    elif choice == "3":
        # Auto-click ngay
        print("⚠️  Bỏ qua kiểm tra pattern, auto-click trực tiếp!")
        time.sleep(1)
        tester.auto_click_10s()

    else:
        print("❌ Lựa chọn không hợp lệ!")


if __name__ == "__main__":
    main()
