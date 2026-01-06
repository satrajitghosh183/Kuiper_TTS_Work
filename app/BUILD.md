# Kuiper TTS - Build Guide

This guide explains how to build Kuiper TTS for Windows, macOS, and Linux.

## Prerequisites

### All Platforms
- Node.js 18+ and npm
- Python 3.10+
- Git

### macOS
- Xcode Command Line Tools (`xcode-select --install`)
- For code signing: Apple Developer ID

### Windows
- Visual Studio Build Tools (for native modules)
- For code signing: Code signing certificate

### Linux
- Build essentials (`sudo apt install build-essential`)
- FUSE (for AppImage): `sudo apt install fuse libfuse2`

## Quick Start

```bash
# Install dependencies
cd app
npm install

# Generate icons (first time only)
npm run generate-icons

# Development mode (with hot reload)
npm run electron:dev

# Build for current platform
npm run electron:build
```

## Build Commands

### Development
```bash
# Start web dev server only
npm run dev

# Start Electron with hot reload
npm run electron:dev
```

### Production Builds

```bash
# Build for current platform (auto-detects)
npm run electron:build

# Build for specific platforms
npm run electron:build:mac    # macOS only
npm run electron:build:win    # Windows only
npm run electron:build:linux  # Linux only

# Build for all platforms (requires cross-compilation setup)
npm run electron:build:all
```

### Output Locations

After building, find your installers in:
- `app/dist-electron/`

Platform-specific outputs:
- **macOS**: `Kuiper TTS-{version}.dmg`, `Kuiper TTS-{version}-arm64.zip`
- **Windows**: `Kuiper TTS Setup {version}.exe`, `Kuiper TTS-{version}-portable.exe`
- **Linux**: `Kuiper TTS-{version}-x64.AppImage`, `kuiper-tts_{version}_amd64.deb`

## Cross-Platform Building

### Building for Other Platforms

To build for other platforms from your current OS:

#### From macOS
```bash
# Windows (requires Wine)
brew install --cask wine-stable
npm run electron:build:win

# Linux
npm run electron:build:linux
```

#### From Windows (WSL2)
```bash
# Linux
npm run electron:build:linux

# Note: macOS builds require a Mac
```

#### Using Docker (Linux builds)
```bash
docker run --rm -v $(pwd):/project -w /project/app \
  electronuserland/builder:wine \
  npm run electron:build:linux
```

### CI/CD Building

For GitHub Actions, see `.github/workflows/build.yml` (if available).

## Code Signing

### macOS
Set these environment variables:
```bash
export APPLE_ID="your@apple.id"
export APPLE_ID_PASSWORD="app-specific-password"
export APPLE_TEAM_ID="YOURTEAMID"
export CSC_LINK="path/to/certificate.p12"
export CSC_KEY_PASSWORD="certificate-password"
```

### Windows
```bash
export CSC_LINK="path/to/certificate.pfx"
export CSC_KEY_PASSWORD="certificate-password"
```

## Python Backend

The application bundles the Python backend. Users need Python 3.10+ installed on their system.

### First-Time Setup (End Users)
After installation, users should run the setup script:
- **Windows**: Double-click `setup.bat` in the resources folder
- **macOS/Linux**: Run `./setup.sh` in the resources folder

This creates a virtual environment and installs Python dependencies.

## Troubleshooting

### Build Errors

**Missing icons**
```bash
npm run generate-icons
```

**Native module errors**
```bash
npm run clean
rm -rf node_modules
npm install
npm run rebuild
```

**Permission errors (macOS)**
```bash
sudo xattr -rd com.apple.quarantine /Applications/Kuiper\ TTS.app
```

### Runtime Errors

**Python not found**
- Ensure Python 3.10+ is installed and in PATH
- Run the setup script from the resources folder

**GPU not detected**
- Install CUDA drivers for GPU acceleration
- For CPU-only mode, no additional setup needed

## Project Structure

```
app/
├── dist/                 # Vite build output (web assets)
├── dist-electron/        # Electron Builder output (installers)
├── electron/
│   ├── main.cjs         # Main process
│   └── preload.cjs      # Preload script
├── resources/
│   ├── icons/           # App icons (all platforms)
│   └── entitlements.mac.plist
├── scripts/
│   ├── afterPack.js     # Post-build hook
│   └── generate-icons.cjs
├── src/                  # React frontend source
├── electron-builder.yml  # Build configuration
└── package.json
```

## Release Checklist

1. Update version in `package.json`
2. Update changelog (if applicable)
3. Run tests: `npm run lint`
4. Generate fresh icons: `npm run generate-icons`
5. Build for all platforms
6. Test installers on each platform
7. Sign and notarize (for distribution)
8. Create GitHub release (optional)

