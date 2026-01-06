# Kuiper TTS App Icons

This folder should contain the application icons for all platforms.

## Required Files

- `icon.icns` - macOS icon (from 16x16 to 1024x1024)
- `icon.ico` - Windows icon (from 16x16 to 256x256)
- `icon.png` - Linux icon (256x256 or 512x512)
- Linux folder with multiple sizes: 16x16.png, 32x32.png, etc.

## How to Generate

1. Start with `icon.svg` (already created) or create a 1024x1024 PNG
2. Use one of these methods:

### Method 1: electron-icon-builder (Recommended)
```bash
npm install -g electron-icon-builder
electron-icon-builder --input=icon.svg --output=./
```

### Method 2: Online Tools
- https://www.electron.build/icons
- https://iconifier.net/

### Method 3: macOS iconutil
```bash
mkdir icon.iconset
# Create PNG files in iconset folder
iconutil -c icns icon.iconset
```

### Method 4: ImageMagick
```bash
# For ICO
convert icon.png -resize 256x256 icon.ico

# For ICNS (needs icnsutils on Linux or iconutil on macOS)
png2icns icon.icns icon.png
```
