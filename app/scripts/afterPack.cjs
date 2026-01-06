/**
 * After Pack Script for Kuiper TTS
 * Handles post-packaging tasks including Python bundling and environment setup.
 * 
 * This script runs after electron-builder packs the application.
 */

const { exec, execSync } = require('child_process')
const path = require('path')
const fs = require('fs')

// Python requirements for the application
const PYTHON_REQUIREMENTS = `
# Kuiper TTS Python Requirements
# Core web framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
websockets>=12.0
pydantic>=2.0.0

# Audio processing
sounddevice>=0.4.6
soundfile>=0.12.1
librosa>=0.10.1
numpy>=1.24.0

# System utilities
psutil>=5.9.0

# Machine learning (CPU versions for smaller package size)
# Users can install CUDA versions manually for GPU support
torch>=2.0.0
lightning>=2.0.0
`.trim()

// Create a setup script for first-time run
const SETUP_SCRIPT_WINDOWS = `@echo off
echo Setting up Kuiper TTS...
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate and install dependencies
echo Installing dependencies...
call venv\\Scripts\\activate.bat
pip install --upgrade pip
pip install -r python-requirements.txt

echo.
echo Setup complete! You can now run Kuiper TTS.
pause
`

const SETUP_SCRIPT_UNIX = `#!/bin/bash
echo "Setting up Kuiper TTS..."
echo

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Python is not installed. Please install Python 3.10+"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r python-requirements.txt

echo
echo "Setup complete! You can now run Kuiper TTS."
`

exports.default = async function(context) {
  const { appOutDir, packager, targets } = context
  const platform = packager.platform.name
  
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
  console.log('  Kuiper TTS - After Pack Hook')
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
  console.log(`  Platform: ${platform}`)
  console.log(`  Output: ${appOutDir}`)
  console.log('')
  
  // Determine resources directory based on platform
  let resourcesDir
  
  if (platform === 'darwin') {
    // macOS: Resources is inside the .app bundle
    resourcesDir = path.join(
      appOutDir, 
      `${packager.appInfo.productName}.app`, 
      'Contents', 
      'Resources'
    )
  } else {
    // Windows and Linux: resources folder at root
    resourcesDir = path.join(appOutDir, 'resources')
  }
  
  console.log(`  Resources directory: ${resourcesDir}`)
  
  // Ensure resources directory exists
  if (!fs.existsSync(resourcesDir)) {
    fs.mkdirSync(resourcesDir, { recursive: true })
  }
  
  // 1. Create Python requirements file
  console.log('\n📦 Creating Python requirements...')
  const requirementsPath = path.join(resourcesDir, 'python-requirements.txt')
  fs.writeFileSync(requirementsPath, PYTHON_REQUIREMENTS)
  console.log('   ✓ Created python-requirements.txt')
  
  // 2. Create platform-specific setup scripts
  console.log('\n📝 Creating setup scripts...')
  
  if (platform === 'win32') {
    const setupPath = path.join(resourcesDir, 'setup.bat')
    fs.writeFileSync(setupPath, SETUP_SCRIPT_WINDOWS)
    console.log('   ✓ Created setup.bat (Windows)')
  } else {
    const setupPath = path.join(resourcesDir, 'setup.sh')
    fs.writeFileSync(setupPath, SETUP_SCRIPT_UNIX)
    fs.chmodSync(setupPath, '755')
    console.log('   ✓ Created setup.sh (Unix)')
  }
  
  // 3. Create app configuration file
  console.log('\n⚙️  Creating app configuration...')
  const appConfig = {
    name: packager.appInfo.productName,
    version: packager.appInfo.version,
    buildDate: new Date().toISOString(),
    platform: platform,
    pythonRequired: '>=3.10',
    requirements: {
      minRam: '8GB',
      recommendedRam: '16GB',
      gpuRecommended: true
    }
  }
  
  const configPath = path.join(resourcesDir, 'app-config.json')
  fs.writeFileSync(configPath, JSON.stringify(appConfig, null, 2))
  console.log('   ✓ Created app-config.json')
  
  // 4. Create README for the resources folder
  console.log('\n📄 Creating documentation...')
  const readme = `# Kuiper TTS Resources

This folder contains resources required by Kuiper TTS.

## First-Time Setup

Before running the application, you need to set up the Python environment:

### Windows
1. Double-click \`setup.bat\`
2. Wait for installation to complete
3. Run Kuiper TTS

### macOS / Linux
1. Open Terminal in this folder
2. Run: \`./setup.sh\`
3. Wait for installation to complete
4. Run Kuiper TTS

## Requirements

- Python 3.10 or higher
- 8GB RAM minimum (16GB recommended)
- GPU with CUDA support (optional, for faster training)

## Troubleshooting

If you encounter issues:

1. Make sure Python 3.10+ is installed
2. Check that you have enough disk space (at least 5GB)
3. On macOS, you may need to allow the app in System Preferences > Security

For GPU support on Windows/Linux:
\`\`\`bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu118
\`\`\`
`
  
  const readmePath = path.join(resourcesDir, 'README.txt')
  fs.writeFileSync(readmePath, readme)
  console.log('   ✓ Created README.txt')
  
  // 5. Verify backend files were copied
  console.log('\n🔍 Verifying backend files...')
  const backendDir = path.join(resourcesDir, 'backend')
  
  if (fs.existsSync(backendDir)) {
    const files = fs.readdirSync(backendDir, { recursive: true })
    const pyFiles = files.filter(f => f.toString().endsWith('.py'))
    console.log(`   ✓ Backend directory found with ${pyFiles.length} Python files`)
  } else {
    console.log('   ⚠️  Backend directory not found - will be created by extraResources')
  }
  
  // 6. Log completion
  console.log('')
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
  console.log('  After Pack completed successfully!')
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
  console.log('')
}
