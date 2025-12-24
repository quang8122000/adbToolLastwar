#!/bin/bash

echo "🔨 Bắt đầu build SimpleMonitor.app..."
echo ""

# Xóa thư mục build cũ nếu có
if [ -d "build" ]; then
    echo "🗑️  Xóa thư mục build cũ..."
    rm -rf build
fi

if [ -d "dist/SimpleMonitor.app" ]; then
    echo "🗑️  Xóa app cũ..."
    rm -rf dist/SimpleMonitor.app
fi

echo ""
echo "📦 Chạy PyInstaller..."
pyinstaller SimpleMonitor.spec --clean

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build thành công!"
    echo "📱 App đã được tạo tại: dist/SimpleMonitor.app"
    echo ""
    echo "🚀 Mở app..."
    open dist/SimpleMonitor.app
else
    echo ""
    echo "❌ Build thất bại!"
    exit 1
fi
