#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script để theo dõi game Last War và thông báo khi xuất hiện chữ "Đào Kho Báu"
"""

import subprocess
import time
import os
import re
import threading
from datetime import datetime

try:
    from PIL import Image, ImageEnhance
    import pytesseract
    import numpy as np

    OCR_AVAILABLE = True
    NUMPY_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    NUMPY_AVAILABLE = False

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class GameMonitor:
    def __init__(
        self,
        package_name,
        target_text,
        use_ocr=False,
        debug=False,
        auto_click=False,
        click_delay=0.3,
        click_speed=0.07,
        click_duration=10,
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
        self.click_speed = click_speed  # Tốc độ click (interval giữa các lần click)
        self.click_duration = click_duration  # Thời gian click liên tục ở bước 5
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
        self._pattern_rgb_cache = {}  # Cache RGB values của patterns

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

            # Không resize để giữ nguyên chi tiết (ưu tiên độ chính xác hơn tốc độ)
            crop_width, crop_height = img_crop.size
            img_resized = img_crop  # Giữ nguyên kích thước gốc

            # Preprocessing để cải thiện OCR
            # 1. Chuyển sang grayscale
            img_gray = img_resized.convert("L")

            # 2. Tăng contrast
            if NUMPY_AVAILABLE:
                img_array = np.array(img_gray)
                # Simple contrast enhancement: clip and normalize
                img_array = np.clip(img_array * 1.2, 0, 255).astype(np.uint8)
                img_enhanced = Image.fromarray(img_array)
            else:
                # Fallback: dùng ImageEnhance nếu không có numpy
                enhancer = ImageEnhance.Contrast(img_gray)
                img_enhanced = enhancer.enhance(1.5)

            # 3. Sharpen để làm rõ text
            sharpener = ImageEnhance.Sharpness(img_enhanced)
            img_final = sharpener.enhance(2.0)

            # Debug: Lưu ảnh preprocessing để kiểm tra
            if self.debug:
                try:
                    img_final.save("/tmp/ocr_preprocessed.png")
                    print(
                        f"[DEBUG] Đã lưu ảnh preprocessing tại: /tmp/ocr_preprocessed.png"
                    )
                except:
                    pass

            # Tesseract config tối ưu cho text detection
            # Thử nhiều PSM modes để tăng khả năng nhận diện
            psm_modes = [
                ("--oem 3 --psm 6", "Single uniform block"),  # Phù hợp nhất cho UI game
                ("--oem 3 --psm 11", "Sparse text"),  # Backup: text rải rác
                ("--oem 3 --psm 3", "Fully automatic"),  # Fallback: tự động
            ]

            text = ""
            data = None

            for tesseract_config, mode_desc in psm_modes:
                # Nhận dạng text từ ảnh đã preprocessing
                try:
                    text_temp = pytesseract.image_to_string(
                        img_final, lang="eng", config=tesseract_config
                    )

                    # Kiểm tra xem có tìm thấy target text không
                    found_any = any(
                        target.lower() in text_temp.lower()
                        for target in self.target_texts
                    )

                    if (
                        found_any or not text
                    ):  # Dùng result này nếu tìm thấy hoặc chưa có result nào
                        text = text_temp
                        data = pytesseract.image_to_data(
                            img_final,
                            lang="eng",
                            config=tesseract_config,
                            output_type=pytesseract.Output.DICT,
                        )

                        if self.debug:
                            print(
                                f"[DEBUG] Sử dụng PSM mode: {mode_desc} ({tesseract_config})"
                            )

                        if found_any:
                            break  # Đã tìm thấy, không cần thử mode khác

                except Exception as e:
                    if self.debug:
                        print(f"[DEBUG] Lỗi khi OCR với mode {mode_desc}: {e}")
                    continue

            # Tìm tọa độ cho tất cả target texts
            for target in self.target_texts:
                if target in text:
                    self.target_text = target  # Lưu text đã tìm thấy
                    # Tính toạ độ cho text này
                    coords = self.find_text_coordinates_for_target(data, target)
                    if coords:
                        # Không cần scale vì không resize nữa, chỉ cần cộng offset (do crop)
                        self.last_found_coords = (
                            coords[0] + crop_offset_x,
                            coords[1] + crop_offset_y,
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
        """Kiểm tra pixel pattern có khớp không - OPTIMIZED VERSION

        Args:
            pattern_name: Tên pattern cần check (vd: 'step3', 'step4')
            tolerance: Độ sai lệch màu cho phép (0-255), None = dùng self.pattern_tolerance

        Returns:
            Tuple (is_match, match_ratio)
        """
        if not self.pixel_patterns or pattern_name not in self.pixel_patterns:
            print(f"⚠️  CẢNH BÁO: Không tìm thấy pattern '{pattern_name}' trong config!")
            if self.debug:
                print(f"[DEBUG] Available patterns: {list(self.pixel_patterns.keys())}")
            return False, 0.0  # Return False khi không tìm thấy pattern

        if tolerance is None:
            tolerance = self.pattern_tolerance

        pattern = self.pixel_patterns[pattern_name]
        total_pixels = len(pattern)

        # Chụp screenshot mới nếu chưa có cache
        if not self.cached_screenshot:
            self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
            self.run_adb_command(
                "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
            )
            self.cached_screenshot = Image.open("/tmp/screenshot.png")

        img = self.cached_screenshot

        # ⚡ OPTIMIZATION 1: Parse tất cả expected RGB một lần và cache
        cache_key = pattern_name
        if cache_key not in self._pattern_rgb_cache:
            self._pattern_rgb_cache[cache_key] = [
                (
                    p["coord"],
                    int(p["color"][1:3], 16),
                    int(p["color"][3:5], 16),
                    int(p["color"][5:7], 16),
                    p["color"],
                )
                for p in pattern
            ]

        cached_pattern = self._pattern_rgb_cache[cache_key]

        # ⚡ OPTIMIZATION 2: Dùng numpy nếu có (nhanh hơn 3-5x)
        if NUMPY_AVAILABLE:
            # Convert image sang numpy array một lần
            img_array = np.array(img)
            matched_pixels = 0

            # Early stopping threshold
            min_required_matches = int(total_pixels * self.pattern_match_ratio)
            max_allowed_failures = total_pixels - min_required_matches
            failed_pixels = 0

            for coord, exp_r, exp_g, exp_b, exp_color in cached_pattern:
                x, y = coord

                # ⚡ OPTIMIZATION 3: Early stopping
                if failed_pixels > max_allowed_failures:
                    if self.debug:
                        print(
                            f"[DEBUG] ⚡ Early stop: Quá nhiều pixel fail ({failed_pixels}/{max_allowed_failures})"
                        )
                    break

                try:
                    # Lấy màu từ numpy array (nhanh hơn getpixel)
                    actual_r, actual_g, actual_b = img_array[y, x, :3]

                    # Tính độ sai khác
                    diff = (
                        abs(int(actual_r) - exp_r)
                        + abs(int(actual_g) - exp_g)
                        + abs(int(actual_b) - exp_b)
                    )

                    if diff <= tolerance * 3:
                        matched_pixels += 1
                        if self.debug:
                            actual_color = (
                                f"#{actual_r:02x}{actual_g:02x}{actual_b:02x}".upper()
                            )
                            print(
                                f"[DEBUG] ✅ Pixel ({x},{y}): {actual_color} ≈ {exp_color} (diff={diff})"
                            )
                    else:
                        failed_pixels += 1
                        if self.debug:
                            actual_color = (
                                f"#{actual_r:02x}{actual_g:02x}{actual_b:02x}".upper()
                            )
                            print(
                                f"[DEBUG] ❌ Pixel ({x},{y}): {actual_color} ≠ {exp_color} (diff={diff})"
                            )
                except Exception as e:
                    failed_pixels += 1
                    if self.debug:
                        print(f"[DEBUG] ⚠️  Lỗi khi check pixel ({x},{y}): {e}")
        else:
            # Fallback: Dùng PIL getpixel (chậm hơn)
            matched_pixels = 0
            min_required_matches = int(total_pixels * self.pattern_match_ratio)
            max_allowed_failures = total_pixels - min_required_matches
            failed_pixels = 0

            for coord, exp_r, exp_g, exp_b, exp_color in cached_pattern:
                x, y = coord

                if failed_pixels > max_allowed_failures:
                    break

                try:
                    actual_pixel = img.getpixel((x, y))
                    actual_color = "#{:02x}{:02x}{:02x}".format(
                        actual_pixel[0], actual_pixel[1], actual_pixel[2]
                    ).upper()

                    diff = (
                        abs(actual_pixel[0] - exp_r)
                        + abs(actual_pixel[1] - exp_g)
                        + abs(actual_pixel[2] - exp_b)
                    )

                    if diff <= tolerance * 3:
                        matched_pixels += 1
                        if self.debug:
                            print(
                                f"[DEBUG] ✅ Pixel ({x},{y}): {actual_color} ≈ {exp_color} (diff={diff})"
                            )
                    else:
                        failed_pixels += 1
                        if self.debug:
                            print(
                                f"[DEBUG] ❌ Pixel ({x},{y}): {actual_color} ≠ {exp_color} (diff={diff})"
                            )
                except Exception as e:
                    failed_pixels += 1
                    if self.debug:
                        print(f"[DEBUG] ⚠️  Lỗi khi check pixel ({x},{y}): {e}")

        # Dùng match_ratio từ config
        match_ratio = matched_pixels / total_pixels
        is_match = match_ratio >= self.pattern_match_ratio

        if self.debug:
            print(
                f"[DEBUG] Pattern '{pattern_name}': {matched_pixels}/{total_pixels} pixels khớp ({match_ratio*100:.1f}%) -> {'✅ PASS' if is_match else '❌ FAIL'}"
            )

        return is_match, match_ratio

    def click_at_coordinates(self, x, y):
        """Click vào tọa độ trên màn hình"""
        cmd = f"adb shell input tap {x} {y}"
        self.run_adb_command(cmd)
        print(f"👆 Đã click vào tọa độ ({x}, {y})")

    def smart_verify_pattern(self, pattern_name, max_delay=0.3):
        """Smart Adaptive Verification - Tự động quyết định số lần verify dựa trên match ratio

        Logic:
        - Match ratio >= 95%: Chỉ cần 1 lần check (rất chắc chắn)
        - Match ratio 80-95%: Verify 2 lần với delay 0.1s (khá chắc chắn)
        - Match ratio < 80%: Verify 3 lần với delay 0.15s (không chắc chắn)

        Args:
            pattern_name: Tên pattern cần check
            max_delay: Delay tối đa giữa các lần check (mặc định 0.3s)

        Returns:
            True nếu pattern ổn định, False nếu không
        """
        # Chụp screenshot lần đầu
        self.cached_screenshot = None
        self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
        self.run_adb_command(
            "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
        )
        self.cached_screenshot = Image.open("/tmp/screenshot.png")

        # Check lần đầu và lấy match_ratio
        is_match, match_ratio = self.check_pixel_pattern(pattern_name)

        if not is_match:
            if self.debug:
                print(f"[DEBUG] 🔴 Lần 1: Không khớp ({match_ratio*100:.1f}%)")
            return False

        # Quyết định số lần verify dựa trên match_ratio
        if match_ratio >= 0.95:
            # Rất chắc chắn - chỉ cần 1 lần
            if self.debug:
                print(
                    f"[DEBUG] 🟢 Match ratio cao ({match_ratio*100:.1f}%) - Chỉ cần 1 lần check"
                )
            return True

        elif match_ratio >= 0.80:
            # Khá chắc chắn - verify 2 lần
            num_checks = 2
            delay = 0.1
            if self.debug:
                print(
                    f"[DEBUG] 🟡 Match ratio trung bình ({match_ratio*100:.1f}%) - Verify {num_checks} lần"
                )
        else:
            # Không chắc chắn - verify 3 lần
            num_checks = 3
            delay = 0.15
            if self.debug:
                print(
                    f"[DEBUG] 🟠 Match ratio thấp ({match_ratio*100:.1f}%) - Verify {num_checks} lần"
                )

        # Verify thêm (num_checks - 1) lần nữa
        for i in range(1, num_checks):
            time.sleep(delay)

            # Chụp screenshot mới
            self.cached_screenshot = None
            self.run_adb_command("adb shell screencap -p /sdcard/screenshot.png")
            self.run_adb_command(
                "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null"
            )
            self.cached_screenshot = Image.open("/tmp/screenshot.png")

            # Check
            is_match, match_ratio = self.check_pixel_pattern(pattern_name)
            if not is_match:
                if self.debug:
                    print(f"[DEBUG] 🔴 Lần {i+1}: Không khớp ({match_ratio*100:.1f}%)")
                return False

            if self.debug:
                print(f"[DEBUG] 🟢 Lần {i+1}: Khớp ({match_ratio*100:.1f}%)")

        return True

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

    def step1_click_treasure(self):
        """Bước 1: Click vào text 'Dig Up Treasure'"""
        if self.last_found_coords:
            x, y = self.last_found_coords
            print(f"🎯 Bước 1: Click vào '{self.target_text}'...")
            time.sleep(self.click_delay)
            self.click_at_coordinates(x, y)
            time.sleep(self.click_delay * 2)
            return True
        else:
            print(f"⚠️  Không tìm thấy tọa độ để click")
            return False

    def step2_click_center(self):
        """Bước 2: Click vào tọa độ giữa màn hình"""
        print(f"🎯 Bước 2: Click vào tọa độ giữa màn hình...")
        time.sleep(self.click_delay)
        self.click_at_coordinates(514, 819)
        time.sleep(self.click_delay * 2)
        return True

    def step3_verify_and_click(self):
        """Bước 3: Kiểm tra pixel pattern và click (550, 1136)"""
        print(f"🔍 Bước 3: Kiểm tra pixel pattern tại (550, 1136) (Smart Verify)...")
        time.sleep(self.click_delay)

        # Chọn pattern dựa trên target_text
        if "Test Flight" in self.target_text:
            pattern_name = "step3_test"
        elif any(
            word in self.target_text for word in ["Wondrous", "Christmas", "Party"]
        ):
            pattern_name = "step3_tiec"
        else:
            pattern_name = "step3_dig"

        # Kiểm tra pattern có tồn tại không
        if pattern_name not in self.pixel_patterns:
            print(f"⚠️  Pattern '{pattern_name}' không tồn tại trong config!")
            # Thử dùng pattern còn lại
            fallback = "step3_dig" if pattern_name == "step3_test" else "step3_test"
            if fallback in self.pixel_patterns:
                print(f"🔄 Thử dùng pattern fallback: '{fallback}'")
                pattern_name = fallback
            else:
                print(f"❌ Không có pattern nào cho bước 3. Bỏ qua verify.")
                return False

        if self.smart_verify_pattern(pattern_name):
            print(f"✅ Pattern ổn định! Click vào (550, 1136)...")
            time.sleep(self.click_delay)
            self.click_at_coordinates(550, 1136)
            time.sleep(self.click_delay * 2)
            return True
        else:
            print(f"⚠️  Pattern không ổn định (có thể bị nhiễu UI).")
            return False

    def step4_verify_and_click(self):
        """Bước 4: Kiểm tra pixel pattern và click (538, 1470)"""
        print(f"🔍 Bước 4: Kiểm tra pixel pattern tại (538, 1470) (Smart Verify)...")

        max_retries = 2
        for attempt in range(max_retries):
            if self.stop_requested:
                return False

            if attempt > 0:
                print(f"🔄 Thử lại lần {attempt + 1}/{max_retries}...")
                time.sleep(0.5)

            if self.smart_verify_pattern("step4"):
                print(f"✅ Pattern ổn định! Click vào (538, 1470)...")
                time.sleep(self.click_delay)
                self.click_at_coordinates(538, 1470)
                time.sleep(self.click_delay * 2)
                return True

        print(f"⚠️  Pixel pattern không khớp sau {max_retries} lần thử.")
        return False

    def step5_auto_click(self):
        """Bước 5: Kiểm tra pixel pattern và auto-click liên tục cho đến khi quà xuất hiện"""
        print(f"🔍 Bước 5: Kiểm tra pixel pattern tại (514, 819)...")
        print(
            f"⏰  Sẽ click liên tục và kiểm tra đến khi quà xuất hiện (timeout: 10 phút)..."
        )

        max_wait_time = 600  # 10 phút
        check_interval = 1.5
        step5_start_time = time.time()
        attempt = 0

        while time.time() - step5_start_time < max_wait_time:
            if self.stop_requested:
                print("\n🛑 Nhận lệnh dừng tại Bước 5")
                return False

            attempt += 1
            elapsed_step5 = time.time() - step5_start_time
            remaining_time = max_wait_time - elapsed_step5

            if attempt > 1:
                print(
                    f"🔄 Lần thử #{attempt} - Còn {remaining_time:.0f}s (đã chờ {elapsed_step5:.0f}s)..."
                )

            if self.smart_verify_pattern("step5"):
                print(
                    f"✅ Pattern ổn định sau {attempt} lần thử ({elapsed_step5:.1f}s)!"
                )
                print(f"🎯 Bắt đầu click liên tục cho đến khi quà xuất hiện...")

                click_start_time = time.time()
                click_interval = self.click_speed
                click_count = {"value": 0}  # Dùng dict để share giữa threads
                should_stop_clicking = {"value": False}  # Flag để dừng click thread
                gift_appeared = {"value": False}  # Flag đánh dấu quà đã xuất hiện

                # Thread 1: Click liên tục không nghỉ
                def click_continuously():
                    while not should_stop_clicking["value"]:
                        if self.stop_requested:
                            should_stop_clicking["value"] = True
                            return

                        if time.time() - step5_start_time > max_wait_time:
                            should_stop_clicking["value"] = True
                            return

                        self.click_at_coordinates(514, 819)
                        click_count["value"] += 1

                        # Hiển thị progress mỗi 20 lần click
                        if click_count["value"] % 20 == 0:
                            elapsed_click = time.time() - click_start_time
                            print(
                                f"⚡ Đã click {click_count['value']} lần ({elapsed_click:.1f}s)..."
                            )

                        time.sleep(click_interval)

                # Thread 2: Kiểm tra pattern định kỳ
                def check_pattern_periodically():
                    check_every_seconds = 2.0
                    last_check_time = time.time()

                    while not should_stop_clicking["value"]:
                        current_time = time.time()

                        if current_time - last_check_time >= check_every_seconds:
                            elapsed_click = current_time - click_start_time
                            print(
                                f"🔍 Kiểm tra xem quà đã xuất hiện chưa (đã click {click_count['value']} lần, {elapsed_click:.1f}s)..."
                            )

                            try:
                                # Clear cache để chụp screenshot mới
                                self.cached_screenshot = None

                                # Kiểm tra xem pattern step5 còn không
                                is_match, match_ratio = self.check_pixel_pattern(
                                    "step5"
                                )

                                if not is_match:
                                    # Pattern biến mất = màn hình đã chuyển = quà đã xuất hiện!
                                    elapsed_total = time.time() - click_start_time
                                    print(
                                        f"✅ Quà đã xuất hiện! Đã click {click_count['value']} lần trong {elapsed_total:.1f}s"
                                    )
                                    gift_appeared["value"] = True
                                    should_stop_clicking["value"] = True
                                    return
                                else:
                                    # Pattern vẫn còn = vẫn đang đếm ngược, tiếp tục click
                                    print(
                                        f"⏳ Vẫn đang đếm ngược (pattern match: {match_ratio*100:.0f}%), tiếp tục click..."
                                    )

                            except Exception as e:
                                # Nếu lỗi khi check, không dừng mà tiếp tục
                                print(f"⚠️  Lỗi khi kiểm tra pattern: {e}")
                                print(
                                    f"   → Tiếp tục click, sẽ thử kiểm tra lại sau {check_every_seconds}s..."
                                )

                            last_check_time = current_time

                        time.sleep(0.1)  # Check mỗi 0.1s xem đã đến giờ check chưa

                # Bắt đầu cả 2 threads
                click_thread = threading.Thread(target=click_continuously, daemon=True)
                check_thread = threading.Thread(
                    target=check_pattern_periodically, daemon=True
                )

                click_thread.start()
                check_thread.start()

                # Đợi cả 2 threads hoàn thành
                click_thread.join()
                check_thread.join()

                # Kiểm tra kết quả
                if gift_appeared["value"]:
                    return True
                elif self.stop_requested:
                    print(f"\n🛑 Nhận lệnh dừng (đã click {click_count['value']} lần)")
                    return False
                else:
                    print(
                        f"\n⏰ Timeout sau {max_wait_time}s (đã click {click_count['value']} lần)"
                    )
                    return False

            time.sleep(check_interval)

        print(f"⚠️  Pixel pattern không khớp sau {attempt} lần thử ({max_wait_time}s).")
        return False

    def execute_click_sequence(self):
        """Thực hiện chuỗi click theo thứ tự"""
        start_time = time.time()

        # Bước 1
        if not self.step1_click_treasure():
            return
        if self.stop_requested:
            print("\n🛑 Nhận lệnh dừng sau Bước 1")
            return

        # Bước 2
        print()
        self.step2_click_center()
        if self.stop_requested:
            print("\n🛑 Nhận lệnh dừng sau Bước 2")
            return

        # Bước 3
        print()
        if not self.step3_verify_and_click():
            print(f"Bỏ qua bước 3 và 4.")
            self.click_back_and_restart()
            return
        if self.stop_requested:
            print("\n🛑 Nhận lệnh dừng sau Bước 3")
            return

        # Bước 4
        print()
        if not self.step4_verify_and_click():
            elapsed_time = time.time() - start_time
            print(f"Bỏ qua bước 4 và 5.")
            print(f"⏱️  Thời gian đã thực hiện: {elapsed_time:.2f}s")
            self.click_back_and_restart()
            return
        if self.stop_requested:
            print("\n🛑 Nhận lệnh dừng sau Bước 4")
            return

        # Bước 5
        print()
        self.step5_auto_click()
        elapsed_time = time.time() - start_time
        print(f"⏱️  Thời gian đã thực hiện: {elapsed_time:.2f}s")

        # Reset về ban đầu sau khi hoàn thành bước 5 (dù thành công hay thất bại)
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
        "step3_dig": [  # Pattern cho "Dig Up Treasure"
            {"coord": (550, 1136), "color": "#FFFFFF"},  # Pixel chính
            {"coord": (545, 1136), "color": "#F8FBF9"},  # Trái
        ],
        "step3_test": [  # Pattern cho "Test Flight Failure"
            {"coord": (550, 1136), "color": "#FFFFFF"},  # Pixel chính
            {"coord": (545, 1136), "color": "#308E4D"},  # Trái (màu khác)
        ],
        "step3_tiec": [  # Pattern cho "Wondrous Christmas Party"
            {"coord": (552, 1723), "color": "#FFFFFF"},  # Pixel chính
            {"coord": (547, 1723), "color": "#FFFFFF"},  # Trái
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
