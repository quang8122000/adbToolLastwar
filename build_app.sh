#!/bin/bash

# Script để build app từ Python code

echo "🔨 Building Last War Monitor App..."

# Check if pyinstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "📦 Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Build app
echo "🚀 Creating macOS app bundle..."
pyinstaller --name="LastWarMonitor" \
    --windowed \
    --onedir \
    --add-data="monitor_game.py:." \
    --noconfirm \
    --clean \
    monitor_game_gui.py

echo ""
echo "✅ Build complete!"
echo "📱 App location: dist/LastWarMonitor.app"
echo ""
echo "📝 To run:"
echo "   open dist/LastWarMonitor.app"
echo ""
echo "📦 To install:"
echo "   cp -r dist/LastWarMonitor.app /Applications/"
