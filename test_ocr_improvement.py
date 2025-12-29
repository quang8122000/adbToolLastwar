#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script test để kiểm tra cải tiến OCR
"""

import subprocess
from PIL import Image, ImageEnhance
import pytesseract
import numpy as np


def test_ocr():
    print("🔍 Kiểm tra cải tiến OCR...")
    print("=" * 60)

    # Chụp screenshot
    print("\n1️⃣ Chụp screenshot...")
    subprocess.run(
        "adb shell screencap -p /sdcard/screenshot.png", shell=True, check=True
    )
    subprocess.run(
        "adb pull /sdcard/screenshot.png /tmp/screenshot.png 2>/dev/null",
        shell=True,
        check=True,
    )
    print("✅ Đã chụp screenshot")

    # Load image
    img = Image.open("/tmp/screenshot.png")
    width, height = img.size
    print(f"📐 Kích thước: {width}x{height}px")

    # Crop vùng OCR (70% phần dưới)
    top = int(height * 0.7)
    img_crop = img.crop((0, top, width, height))
    print(f"✂️  Đã crop vùng OCR: (0,{top}) -> ({width},{height})")

    # Preprocessing
    print("\n2️⃣ Preprocessing ảnh...")

    # Grayscale
    img_gray = img_crop.convert("L")
    print("   ✅ Chuyển sang grayscale")

    # Tăng contrast
    img_array = np.array(img_gray)
    img_array = np.clip(img_array * 1.2, 0, 255).astype(np.uint8)
    img_enhanced = Image.fromarray(img_array)
    print("   ✅ Tăng contrast")

    # Sharpen
    sharpener = ImageEnhance.Sharpness(img_enhanced)
    img_final = sharpener.enhance(2.0)
    print("   ✅ Sharpen")

    # Lưu ảnh để xem
    img_final.save("/tmp/ocr_test_preprocessed.png")
    print(f"\n💾 Đã lưu ảnh preprocessing: /tmp/ocr_test_preprocessed.png")

    # Test với nhiều PSM modes
    print("\n3️⃣ Thử nhiều PSM modes...")
    print("=" * 60)

    psm_modes = [
        ("--oem 3 --psm 6", "Single uniform block"),
        ("--oem 3 --psm 11", "Sparse text"),
        ("--oem 3 --psm 3", "Fully automatic"),
    ]

    results = {}

    for config, desc in psm_modes:
        print(f"\n📝 Mode: {desc} ({config})")
        try:
            text = pytesseract.image_to_string(img_final, lang="eng", config=config)
            results[desc] = text

            # Hiển thị kết quả
            print(f"   Text nhận được ({len(text)} chars):")
            print("   " + "-" * 56)
            for line in text.strip().split("\n")[:10]:  # Chỉ hiển thị 10 dòng đầu
                print(f"   {line}")
            print("   " + "-" * 56)

            # Kiểm tra target texts
            target_texts = ["Test Flight Failure", "Dig Up Treasure"]
            found = []
            for target in target_texts:
                if target.lower() in text.lower():
                    found.append(target)

            if found:
                print(f"   ✅ Tìm thấy: {', '.join(found)}")
            else:
                print(f"   ❌ Không tìm thấy target texts")

        except Exception as e:
            print(f"   ❌ Lỗi: {e}")

    # So sánh
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ TỔNG HỢP:")
    print("=" * 60)

    for desc, text in results.items():
        target_texts = ["Test Flight Failure", "Dig Up Treasure"]
        found = [t for t in target_texts if t.lower() in text.lower()]

        status = "✅" if found else "❌"
        print(f"{status} {desc:30s} - Tìm thấy: {found if found else 'Không có'}")

    print("\n✨ Hoàn tất kiểm tra!")
    print(f"📁 Xem ảnh preprocessing tại: /tmp/ocr_test_preprocessed.png")


if __name__ == "__main__":
    test_ocr()
