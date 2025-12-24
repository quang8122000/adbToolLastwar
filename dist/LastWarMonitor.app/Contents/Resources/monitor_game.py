#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script để theo dõi game Last War và thông báo khi xuất hiện chữ "Đào Kho Báu"
"""

import subprocess
import time
import os
import re
from datetime import datetime

try:
    from PIL import Image
    import pytesseract

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class GameMonitor:
    def __init__(
        self,
        package_name,
        target_text,
        use_ocr=False,
        debug=False,
        auto_click=False,
        click_delay=0.3,
        skip_color_check=False,
        ocr_region=None,
        pixel_patterns=None,
        pattern_tolerance=20,
        pattern_match_ratio=0.6,
    ):
        self.package_name = package_name
        # Hỗ trợ cả string và list
        if isinstance(target_text, str):
            self.target_texts = [target_text]
        else:
            self.target_texts = target_text
        self.target_text = None  # Text được tìm thấy
        self.found = False
        self.use_ocr = use_ocr
        self.debug = debug
        self.auto_click = auto_click
        self.last_found_coords = None
        self.click_delay = click_delay  # Thời gian delay giữa các lần click
        self.cached_screenshot = None  # Cache screenshot để không phải chụp lại
        self.skip_color_check = skip_color_check  # Bỏ qua kiểm tra màu
        self.ocr_region = (
            ocr_region or {}
        )  # Vùng để OCR {top, left, width, height} - hỗ trợ % và px
        self.pixel_patterns = pixel_patterns or {}  # Pixel patterns cho từng bước
        self.pattern_tolerance = pattern_tolerance  # Độ sai lệch màu cho phép (0-255)
        self.pattern_match_ratio = (
            pattern_match_ratio  # Tỷ lệ pixel khớp tối thiểu (0.0-1.0)
        )
        self.stop_requested = False  # Flag để dừng monitor từ GUI

    def parse_dimension(self, value, total):
        """Parse dimension value - hỗ trợ % và px

        Args:
            value: Giá trị string (vd: '30%', '500', '0.3') hoặc số
            total: Tổng kích thước (width hoặc height) để tính %

        Returns:
            int: Giá trị pixel
        """
        if value is None:
            return None

        # Nếu là số thực trong khoảng 0-1, coi như phần trăm
        if isinstance(value, (int, float)):
            if 0 <= value <= 1:
                return int(value * total)
            return int(value)

        # Nếu là string
        value_str = str(value).strip()

        # Kiểm tra %
        if value_str.endswith("%"):
            percent = float(value_str[:-1]) / 100
            return int(percent * total)

        # Kiểm tra số thực 0-1
        try:
            num = float(value_str)
            if 0 <= num <= 1:
                return int(num * total)
            return int(num)
        except ValueError:
            return None

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

    def get_screen_content(self):
        """Lấy nội dung từ màn hình (UI hierarchy hoặc OCR)"""
        if self.use_ocr and OCR_AVAILABLE:
            return self.get_screen_content_ocr()
        else:
            return self.get_screen_content_ui()

    def get_screen_content_ui(self):
        """Lấy nội dung UI hierarchy từ màn hình"""
        # Dump UI hierarchy vào file trên thiết bị
        self.run_adb_command("adb shell uiautomator dump /sdcard/window_dump.xml")

        # Pull file về máy tính
        output = self.run_adb_command("adb shell cat /sdcard/window_dump.xml")

        if self.debug:
            print(
                f"\n[DEBUG] UI Content preview (first 500 chars):\n{output[:500]}...\n"
            )

        return output

    def get_screen_content_ocr(self):
        """Lấy screenshot và nhận dạng text bằng OCR"""
        # Chụp screenshot và lưu vào thiết bị
        self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")

        # Pull screenshot về máy (kết hợp 2 lệnh để nhanh hơn)
        self.run_adb_command(
            "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
        )

        # Mở ảnh và chạy OCR
        try:
            img = Image.open("/tmp/screenshot.png")
            width, height = img.size

            self.cached_screenshot = img  # Cache ảnh gốc để dùng cho get_pixel_color

            # Crop vùng cần OCR nếu có chỉ định
            if self.ocr_region:
                # Parse các giá trị với hỗ trợ % và px
                top = self.parse_dimension(self.ocr_region.get("top", 0), height) or 0
                left = self.parse_dimension(self.ocr_region.get("left", 0), width) or 0
                ocr_width = self.parse_dimension(self.ocr_region.get("width"), width)
                ocr_height = self.parse_dimension(self.ocr_region.get("height"), height)

                # Nếu không có width/height, dùng toàn bộ từ left/top đến cuối
                if ocr_width is None:
                    ocr_width = width - left
                if ocr_height is None:
                    ocr_height = height - top

                # Tính bottom và right
                right = left + ocr_width
                bottom = top + ocr_height

                # Đảm bảo không vượt quá kích thước ảnh
                right = min(right, width)
                bottom = min(bottom, height)

                img_crop = img.crop((left, top, right, bottom))
                crop_offset_x = left
                crop_offset_y = top

                if self.debug:
                    print(
                        f"[DEBUG] Crop vùng OCR: x={left}->{right}, y={top}->{bottom} (kích thước: {right-left}x{bottom-top}px)"
                    )
            else:
                img_crop = img
                crop_offset_x = 0
                crop_offset_y = 0

            # Resize 50% để cân bằng tốc độ và độ chính xác
            crop_width, crop_height = img_crop.size
            img_resized = img_crop.resize(
                (crop_width // 2, crop_height // 2), Image.Resampling.LANCZOS
            )

            # Nhận dạng text từ ảnh đã crop và resize
            data = pytesseract.image_to_data(
                img_resized, lang="eng", output_type=pytesseract.Output.DICT
            )

            # Lấy toàn bộ text để kiểm tra
            text = pytesseract.image_to_string(img_resized, lang="eng")

            # Tìm tọa độ cho tất cả target texts
            for target in self.target_texts:
                if target in text:
                    self.target_text = target  # Lưu text đã tìm thấy
                    # Tính toạ độ cho text này
                    coords = self.find_text_coordinates_for_target(data, target)
                    if coords:
                        # Scale lại tọa độ: nhân 2 (do resize 50%) và cộng offset (do crop)
                        self.last_found_coords = (
                            coords[0] * 2 + crop_offset_x,
                            coords[1] * 2 + crop_offset_y,
                        )
                        break

            if self.debug:
                print(f"\n[DEBUG] OCR detected text:\n{text[:500]}...\n")
                if self.last_found_coords:
                    print(
                        f"[DEBUG] Found '{self.target_text}' at coordinates: {self.last_found_coords}\n"
                    )

            return text
        except Exception as e:
            print(f"⚠️  Lỗi khi OCR: {e}")
            self.cached_screenshot = None
            return ""

    def find_text_coordinates(self, ocr_data):
        """Tìm tọa độ của target text (dùng target_text hiện tại)"""
        if self.target_text:
            return self.find_text_coordinates_for_target(ocr_data, self.target_text)
        return None

    def find_text_coordinates_for_target(self, ocr_data, target_text):
        """Tìm tọa độ của một text cụ thể từ dữ liệu OCR"""
        words = ocr_data["text"]
        n_boxes = len(words)

        # Tìm tất cả các từ trong target text
        target_words = target_text.split()

        for i in range(n_boxes - len(target_words) + 1):
            # Kiểm tra nếu các từ liên tiếp khớp với target text
            match = True
            for j, target_word in enumerate(target_words):
                if words[i + j].lower() != target_word.lower():
                    match = False
                    break

            if match and ocr_data["conf"][i] > 0:  # Confidence > 0
                # Lấy tọa độ của từ đầu tiên
                x = ocr_data["left"][i]
                y = ocr_data["top"][i]
                w = ocr_data["width"][i]
                h = ocr_data["height"][i]

                # Tính tọa độ trung tâm của toàn bộ cụm từ
                last_idx = i + len(target_words) - 1
                x_end = ocr_data["left"][last_idx] + ocr_data["width"][last_idx]
                y_end = ocr_data["top"][last_idx] + ocr_data["height"][last_idx]

                center_x = (x + x_end) // 2
                center_y = (y + y_end) // 2

                return (center_x, center_y)

        return None

    def find_text_coordinates_ui(self, xml_content):
        """Tìm tọa độ của text từ UI hierarchy XML"""
        # Tìm node có text khớp
        pattern = rf'text="{re.escape(self.target_text)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        match = re.search(pattern, xml_content)

        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            return (center_x, center_y)

        return None

    def search_text_in_screen(self):
        """Tìm kiếm text trong màn hình hiện tại"""
        content = self.get_screen_content()

        # Tìm kiếm tất cả các target texts
        for target in self.target_texts:
            if target in content:
                self.target_text = target  # Lưu text đã tìm thấy

                # Nếu dùng UI hierarchy, lấy tọa độ
                if not self.use_ocr:
                    self.last_found_coords = self.find_text_coordinates_ui(content)

                return True

        return False

    def get_pixel_color(self, x, y, use_cache=True):
        """Lấy màu pixel tại tọa độ (x, y)"""
        try:
            # Dùng cached screenshot nếu có (nhanh hơn nhiều)
            if use_cache and self.cached_screenshot:
                img = self.cached_screenshot
            else:
                # Chụp screenshot mới nếu không dùng cache
                self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
                self.run_adb_command(
                    "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
                )
                img = Image.open("/tmp/screenshot.png")

            # Lấy màu pixel
            pixel = img.getpixel((x, y))

            # Chuyển sang mã màu hex
            if len(pixel) >= 3:
                hex_color = "#{:02x}{:02x}{:02x}".format(
                    pixel[0], pixel[1], pixel[2]
                ).upper()
                return hex_color
            return None
        except Exception as e:
            print(f"⚠️  Lỗi khi lấy màu pixel: {e}")
            return None

    def check_pixel_pattern(self, pattern_name, tolerance=None):
        """Kiểm tra pixel pattern có khớp không

        Args:
            pattern_name: Tên pattern cần check (vd: 'step3', 'step4')
            tolerance: Độ sai lệch màu cho phép (0-255), None = dùng self.pattern_tolerance

        Returns:
            True nếu pattern khớp, False nếu không
        """
        if not self.pixel_patterns or pattern_name not in self.pixel_patterns:
            if self.debug:
                print(f"[DEBUG] Không tìm thấy pattern '{pattern_name}'")
            return True  # Nếu không có pattern thì coi như pass

        if tolerance is None:
            tolerance = self.pattern_tolerance

        pattern = self.pixel_patterns[pattern_name]

        # Chụp screenshot mới nếu chưa có cache
        if not self.cached_screenshot:
            self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
            self.run_adb_command(
                "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
            )
            self.cached_screenshot = Image.open("/tmp/screenshot.png")

        img = self.cached_screenshot
        matched_pixels = 0
        total_pixels = len(pattern)

        for pixel_info in pattern:
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

                if diff <= tolerance * 3:  # tolerance cho 3 kênh màu
                    matched_pixels += 1
                    if self.debug:
                        print(
                            f"[DEBUG] ✅ Pixel ({x},{y}): {actual_color} ≈ {expected_color} (diff={diff})"
                        )
                else:
                    if self.debug:
                        print(
                            f"[DEBUG] ❌ Pixel ({x},{y}): {actual_color} ≠ {expected_color} (diff={diff})"
                        )
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] ⚠️  Lỗi khi check pixel ({x},{y}): {e}")

        # Dùng match_ratio từ config
        match_ratio = matched_pixels / total_pixels
        is_match = match_ratio >= self.pattern_match_ratio

        if self.debug:
            print(
                f"[DEBUG] Pattern '{pattern_name}': {matched_pixels}/{total_pixels} pixels khớp ({match_ratio*100:.1f}%) -> {'✅ PASS' if is_match else '❌ FAIL'}"
            )

        return is_match

    def click_at_coordinates(self, x, y):
        """Click vào tọa độ trên màn hình"""
        cmd = f"adb shell input tap {x} {y}"
        self.run_adb_command(cmd)
        print(f"👆 Đã click vào tọa độ ({x}, {y})")

    def stop(self):
        """Yêu cầu dừng monitor"""
        self.stop_requested = True

    def click_back_and_restart(self):
        """Click 3 lần vào tọa độ (537, 1910) để quay lại và chuẩn bị chạy lại"""
        print(f"\n🔄 Click 3 lần vào (537, 1910) để reset...")
        time.sleep(0.3)
        self.click_at_coordinates(537, 1910)
        time.sleep(0.3)
        self.click_at_coordinates(537, 1910)
        time.sleep(0.3)
        self.click_at_coordinates(537, 1910)
        time.sleep(0.5)
        self.click_at_coordinates(537, 1910)
        print(f"✅ Đã reset, sẵn sàng chạy lại từ bước 1\n")

    def execute_click_sequence(self):
        """Thực hiện chuỗi click theo thứ tự"""
        # Bắt đầu đếm thời gian
        start_time = time.time()

        # Bước 1: Click vào text "Dig Up Treasure" (dùng OCR)
        if self.last_found_coords:
            x, y = self.last_found_coords
            print(f"🎯 Bước 1: Click vào '{self.target_text}'...")
            time.sleep(self.click_delay)
            self.click_at_coordinates(x, y)
            time.sleep(self.click_delay * 2)  # Đợi UI phản hồi

        # Check stop request
        if self.stop_requested:
            print("\n🛑 Nhận lệnh dừng sau Bước 1")
            return

        # Bước 2: Click vào tọa độ giữa màn hình (536, 976)
        print(f"\n🎯 Bước 2: Click vào tọa độ giữa màn hình...")
        time.sleep(self.click_delay)
        self.click_at_coordinates(536, 976)
        time.sleep(self.click_delay * 2)  # Đợi UI phản hồi

        # Check stop request
        if self.stop_requested:
            print("\n🛑 Nhận lệnh dừng sau Bước 2")
            return

        # Bước 3: Kiểm tra pixel pattern trước khi click (550, 1136)
        print(f"\n🔍 Bước 3: Kiểm tra pixel pattern tại (550, 1136)...")
        time.sleep(self.click_delay)

        # Chụp screenshot mới cho bước này (sau khi đã click bước 2)
        self.cached_screenshot = None  # Clear cache để chụp lại
        self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
        self.run_adb_command(
            "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
        )
        self.cached_screenshot = Image.open("/tmp/screenshot.png")

        # Kiểm tra pixel pattern
        if self.check_pixel_pattern("step3"):
            print(f"✅ Pixel pattern khớp! Click vào (550, 1136)...")
            time.sleep(self.click_delay)
            self.click_at_coordinates(550, 1136)
        else:
            print(f"⚠️  Pixel pattern không khớp. Bỏ qua bước 3 và 4.")
            self.click_back_and_restart()
            return

        # Đợi UI phản hồi
        time.sleep(self.click_delay * 2)

        # Check stop request
        if self.stop_requested:
            print("\n🛑 Nhận lệnh dừng sau Bước 3")
            return

        # Bước 4: Kiểm tra pixel pattern trước khi click (538, 1470) với retry
        print(f"\n🔍 Bước 4: Kiểm tra pixel pattern tại (538, 1470)...")

        max_retries = 2  # Thử tối đa 2 lần
        step4_success = False

        for attempt in range(max_retries):
            # Check stop request
            if self.stop_requested:
                print("\n🛑 Nhận lệnh dừng tại Bước 4")
                return
            if attempt > 0:
                print(f"🔄 Thử lại lần {attempt + 1}/{max_retries}...")
                time.sleep(0.5)  # Đợi UI ổn định

            # Chụp screenshot mới cho bước 4
            self.cached_screenshot = None
            self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
            self.run_adb_command(
                "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
            )
            self.cached_screenshot = Image.open("/tmp/screenshot.png")

            # Kiểm tra pixel pattern
            if self.check_pixel_pattern("step4"):
                print(f"✅ Pixel pattern khớp! Click vào (538, 1470)...")
                time.sleep(self.click_delay)
                self.click_at_coordinates(538, 1470)
                step4_success = True
                break

        if not step4_success:
            elapsed_time = time.time() - start_time
            print(
                f"⚠️  Pixel pattern không khớp sau {max_retries} lần thử. Bỏ qua bước 4 và 5."
            )
            print(f"⏱️  Thời gian đã thực hiện: {elapsed_time:.2f}s")
            self.click_back_and_restart()
            return

        # Đợi UI phản hồi
        time.sleep(self.click_delay * 2)

        # Bước 5: Kiểm tra pixel pattern và auto-click vào (544, 876) - CHỜ TỐI ĐA 10 PHÚT
        print(f"\n🔍 Bước 5: Kiểm tra pixel pattern tại (514, 819)...")
        print(f"⏰  Sẽ kiểm tra liên tục trong vòng 10 phút...")

        max_wait_time = 600  # 10 phút = 600 giây
        check_interval = 1.5  # Kiểm tra mỗi 1.5 giây
        step5_start_time = time.time()
        step5_success = False
        attempt = 0

        while time.time() - step5_start_time < max_wait_time:
            # Check stop request
            if self.stop_requested:
                print("\n🛑 Nhận lệnh dừng tại Bước 5 (đang chờ pixel pattern)")
                return

            attempt += 1
            elapsed_step5 = time.time() - step5_start_time
            remaining_time = max_wait_time - elapsed_step5

            if attempt > 1:
                print(
                    f"🔄 Lần thử #{attempt} - Còn {remaining_time:.0f}s (đã chờ {elapsed_step5:.0f}s)..."
                )

            # Chụp screenshot mới cho bước 5
            self.cached_screenshot = None
            self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
            self.run_adb_command(
                "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
            )
            self.cached_screenshot = Image.open("/tmp/screenshot.png")

            # Kiểm tra pixel pattern
            if self.check_pixel_pattern("step5"):
                print(
                    f"✅ Pixel pattern khớp sau {attempt} lần thử ({elapsed_step5:.1f}s)!"
                )
                print(
                    f"🎯 Auto-click liên tục vào (544, 876) trong 10 giây (mỗi 70ms)..."
                )

                # Click liên tục trong 10 giây với tốc độ 70ms/lần
                click_start_time = time.time()
                click_duration = 10  # 10 giây
                click_interval = 0.07  # 70 mili giây
                click_count = 0

                while time.time() - click_start_time < click_duration:
                    # Check stop request
                    if self.stop_requested:
                        print(
                            f"\n🛑 Nhận lệnh dừng tại Bước 5 (đã click {click_count} lần)"
                        )
                        return

                    self.click_at_coordinates(544, 876)
                    click_count += 1
                    time.sleep(click_interval)

                print(f"✅ Đã click {click_count} lần trong {click_duration}s")

                # Tính thời gian hoàn thành
                elapsed_time = time.time() - start_time
                print(f"\n🎉 Hoàn thành toàn bộ chuỗi hành động!")
                print(f"⏱️  Tổng thời gian: {elapsed_time:.2f}s")

                # Click 2 lần để reset và chuẩn bị chạy lại
                self.click_back_and_restart()

                step5_success = True
                break

            # Đợi trước khi thử lại
            time.sleep(check_interval)

        if not step5_success:
            elapsed_time = time.time() - start_time
            print(
                f"⚠️  Pixel pattern không khớp sau {attempt} lần thử ({max_wait_time}s). Bỏ qua bước 5."
            )
            print(f"⏱️  Thời gian đã thực hiện: {elapsed_time:.2f}s")
            self.click_back_and_restart()

    def send_notification(self):
        """Gửi thông báo khi tìm thấy text"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"\n{'='*50}\n⚠️  THÔNG BÁO: Đã tìm thấy '{self.target_text}'!\n⏰  Thời gian: {timestamp}\n{'='*50}\n"
        print(message)

        # Tự động thực hiện chuỗi click nếu bật chức năng
        if self.auto_click:
            self.execute_click_sequence()
            # Sau khi hoàn thành chuỗi click (đã reset), tự động tiếp tục loop
            print("🔄 Tự động tiếp tục theo dõi...\n")
            return "y"

        # Liên tục kêu thông báo cho đến khi người dùng phản hồi
        print(
            "\n🔔 Đang kêu thông báo liên tục... Nhấn 'y' để tiếp tục hoặc 'n' để dừng\n"
        )

        # Tạo thread để nhận input từ người dùng
        import threading

        user_responded = threading.Event()
        user_response = {"value": None}

        def get_user_input():
            response = input("👉 Tiếp tục theo dõi? (y/n): ")
            user_response["value"] = response
            user_responded.set()

        # Bắt đầu thread nhận input
        input_thread = threading.Thread(target=get_user_input)
        input_thread.daemon = True
        input_thread.start()

        # Liên tục phát âm thanh và thông báo cho đến khi có phản hồi
        notification_count = 0
        while not user_responded.is_set():
            notification_count += 1
            # Phát âm thanh thông báo (macOS)
            os.system("afplay /System/Library/Sounds/Glass.aiff &")

            # Gửi notification trên macOS
            os.system(
                f"""osascript -e 'display notification "Đã tìm thấy: {self.target_text} (#{notification_count})" with title "⚠️ Game Monitor" sound name "Glass"' &"""
            )

            # Chờ 3 giây trước khi kêu lại
            time.sleep(1)

        # Đợi thread hoàn thành
        input_thread.join(timeout=1)

        return user_response["value"]

    def monitor(self, interval=5):
        """Theo dõi liên tục"""
        print(f"🎮 Bắt đầu theo dõi game: {self.package_name}")
        print(f"🔍 Tìm kiếm text: {self.target_texts}")
        print(f"⏱️  Kiểm tra mỗi {interval} giây")
        print(
            f"📷 Phương thức: {'OCR (nhận dạng hình ảnh)' if self.use_ocr else 'UI Hierarchy'}"
        )
        print(f"🖱️  Tự động click: {'BẬT' if self.auto_click else 'TẮT'}")
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
        try:
            while not self.stop_requested:
                check_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S")

                # Kiểm tra app có đang chạy không
                if not self.check_app_running():
                    print(f"[{timestamp}] ⏸️  App chưa chạy. Chờ app khởi động...")
                    time.sleep(interval)
                    continue

                print(f"[{timestamp}] 🔍 Kiểm tra lần #{check_count}...", end=" ")

                # Tìm kiếm text
                if self.search_text_in_screen():
                    print("✅ Tìm thấy!")
                    response = self.send_notification()
                    self.found = True

                    # Kiểm tra phản hồi người dùng
                    if response and response.lower() != "y":
                        print("🛑 Dừng theo dõi.")
                        break
                    else:
                        self.found = False
                        print("\n🔄 Tiếp tục theo dõi...\n")
                else:
                    print("❌ Chưa tìm thấy")

                time.sleep(interval)

            if self.stop_requested:
                print("\n🛑 Đã nhận lệnh dừng từ GUI.")

        except KeyboardInterrupt:
            print("\n\n🛑 Đã dừng theo dõi bởi người dùng.")
        except Exception as e:
            print(f"\n❌ Lỗi: {e}")


def main():
    # Cấu hình
    PACKAGE_NAME = "com.fun.lastwar.vn.gp"
    # Có thể truyền 1 chuỗi hoặc list nhiều chuỗi
    TARGET_TEXT = [
        "Dig Up Treasure",
        "Test Flight Failure",
    ]  # Tìm 1 trong các text này
    # Hoặc dùng chuỗi đơn: TARGET_TEXT = "Dig Up Treasure"
    CHECK_INTERVAL = 2  # giây - Giảm xuống 2s để check nhanh hơn

    # Tùy chọn
    USE_OCR = True  # Đổi thành True để dùng OCR (chụp màn hình + nhận dạng text)
    AUTO_CLICK = True  # Đổi thành True để tự động click vào text khi tìm thấy
    SKIP_COLOR_CHECK = True  # Đặt True để bỏ qua kiểm tra màu, click thẳng (nhanh hơn!)
    CLICK_DELAY = 0.2  # Thời gian delay giữa các lần click (giây) - Giảm để nhanh hơn
    DEBUG_MODE = False  # Đổi thành True để xem tool đang "nhìn thấy" gì
    OCR_REGION = (0.7, 1.0)  # Chỉ OCR 30% phần dưới màn hình (từ 70% đến 100%)

    # Pixel Pattern - Tăng độ linh hoạt
    PATTERN_TOLERANCE = (
        20  # Độ sai lệch màu cho phép (0-255), càng cao càng dễ khớp. Mặc định: 20
    )
    PATTERN_MATCH_RATIO = (
        0.6  # Tỷ lệ pixel khớp tối thiểu (0.0-1.0). 0.6 = 60% pixel khớp là pass
    )

    # ⭐ PIXEL PATTERNS - Định nghĩa các pixel đặc trưng cho mỗi bước
    # Để lấy pixel patterns: Bật DEBUG_MODE=True, chạy 1 lần, xem tọa độ, rồi dùng get_pixel_color()
    PIXEL_PATTERNS = {
        "step3": [
            {"coord": (550, 1136), "color": "#FFFFFF"},  # Pixel chính
            {"coord": (545, 1136), "color": "#F8FBF9"},  # Trái
        ],
        "step4": [
            {"coord": (538, 1470), "color": "#10B2FB"},  # Pixel chính
            {"coord": (533, 1470), "color": "#10B3FB"},  # Trái
        ],
        "step5": [
            {"coord": (514, 819), "color": "#94C03D"},  # Pixel chính
            {"coord": (509, 819), "color": "#A7F200"},  # Trái
        ],
    }

    if USE_OCR and not OCR_AVAILABLE:
        print("⚠️  Cần cài đặt thư viện OCR:")
        print("   brew install tesseract")
        print("   pip3 install Pillow pytesseract")
        return

    # Tạo monitor và bắt đầu theo dõi
    monitor = GameMonitor(
        PACKAGE_NAME,
        TARGET_TEXT,
        use_ocr=USE_OCR,
        debug=DEBUG_MODE,
        auto_click=AUTO_CLICK,
        click_delay=CLICK_DELAY,
        skip_color_check=SKIP_COLOR_CHECK,
        ocr_region=OCR_REGION,
        pixel_patterns=PIXEL_PATTERNS,
        pattern_tolerance=PATTERN_TOLERANCE,
        pattern_match_ratio=PATTERN_MATCH_RATIO,
    )
    monitor.monitor(interval=CHECK_INTERVAL)


if __name__ == "__main__":
    main()
