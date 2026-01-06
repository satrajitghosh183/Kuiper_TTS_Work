/**
 * Icon Generation Script for Kuiper TTS
 * Generates app icons for macOS, Windows, and Linux from an SVG source.
 * 
 * Usage: node scripts/generate-icons.cjs
 */

const fs = require('fs')
const path = require('path')
const sharp = require('sharp')

const iconsDir = path.join(__dirname, '..', 'resources', 'icons')
const svgPath = path.join(iconsDir, 'icon.svg')

// Icon sizes needed for each platform
const SIZES = {
  mac: [16, 32, 64, 128, 256, 512, 1024],
  win: [16, 24, 32, 48, 64, 128, 256],
  linux: [16, 24, 32, 48, 64, 128, 256, 512]
}

// Ensure output directories exist
function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

// Generate PNG from SVG at a specific size
async function generatePng(size, outputPath) {
  const svgBuffer = fs.readFileSync(svgPath)
  await sharp(svgBuffer)
    .resize(size, size, {
      fit: 'contain',
      background: { r: 0, g: 0, b: 0, alpha: 0 }
    })
    .png()
    .toFile(outputPath)
  console.log(`  ✓ Generated ${path.basename(outputPath)} (${size}x${size})`)
}

// Generate macOS iconset
async function generateMacIcons() {
  console.log('\n📱 Generating macOS icons...')
  const iconsetDir = path.join(iconsDir, 'icon.iconset')
  ensureDir(iconsetDir)
  
  // macOS expects specific naming convention
  const macSizes = [
    { size: 16, name: 'icon_16x16.png' },
    { size: 32, name: 'icon_16x16@2x.png' },
    { size: 32, name: 'icon_32x32.png' },
    { size: 64, name: 'icon_32x32@2x.png' },
    { size: 128, name: 'icon_128x128.png' },
    { size: 256, name: 'icon_128x128@2x.png' },
    { size: 256, name: 'icon_256x256.png' },
    { size: 512, name: 'icon_256x256@2x.png' },
    { size: 512, name: 'icon_512x512.png' },
    { size: 1024, name: 'icon_512x512@2x.png' },
  ]
  
  for (const { size, name } of macSizes) {
    await generatePng(size, path.join(iconsetDir, name))
  }
  
  console.log('\n  ℹ️  To create icon.icns, run:')
  console.log(`     iconutil -c icns "${iconsetDir}" -o "${path.join(iconsDir, 'icon.icns')}"`)
  
  return iconsetDir
}

// Generate Windows ICO using png2icons
async function generateWindowsIcon() {
  console.log('\n🪟 Generating Windows icon...')
  const png2icons = require('png2icons')
  
  // Generate a 256x256 PNG first (used as source for ICO)
  const pngPath = path.join(iconsDir, 'icon-256.png')
  await generatePng(256, pngPath)
  
  // Read the PNG and convert to ICO
  const pngBuffer = fs.readFileSync(pngPath)
  const icoBuffer = png2icons.createICO(pngBuffer, png2icons.BICUBIC, 0, true, true)
  
  if (icoBuffer) {
    const icoPath = path.join(iconsDir, 'icon.ico')
    fs.writeFileSync(icoPath, icoBuffer)
    console.log(`  ✓ Generated icon.ico`)
  } else {
    console.log('  ❌ Failed to generate ICO')
  }
  
  // Clean up temp file
  fs.unlinkSync(pngPath)
}

// Generate Linux PNG icons
async function generateLinuxIcons() {
  console.log('\n🐧 Generating Linux icons...')
  
  for (const size of SIZES.linux) {
    const pngPath = path.join(iconsDir, `${size}x${size}.png`)
    await generatePng(size, pngPath)
  }
  
  // Also generate main icon.png (512x512)
  await generatePng(512, path.join(iconsDir, 'icon.png'))
}

// Main function
async function main() {
  console.log('🎨 Kuiper TTS Icon Generator')
  console.log('============================')
  
  // Check if source SVG exists
  if (!fs.existsSync(svgPath)) {
    console.error(`❌ Source SVG not found: ${svgPath}`)
    console.log('\nCreating default SVG icon...')
    createDefaultSvg()
  }
  
  ensureDir(iconsDir)
  
  try {
    // Generate all platform icons
    const iconsetDir = await generateMacIcons()
    await generateWindowsIcon()
    await generateLinuxIcons()
    
    console.log('\n✅ Icon generation complete!')
    console.log('\n📋 Next steps:')
    console.log('   1. On macOS, run the iconutil command above to create icon.icns')
    console.log('   2. Icons are ready for electron-builder')
    console.log('')
    
    // Try to run iconutil on macOS
    if (process.platform === 'darwin') {
      const { exec } = require('child_process')
      const icnsPath = path.join(iconsDir, 'icon.icns')
      
      console.log('   Running iconutil to create icon.icns...')
      exec(`iconutil -c icns "${iconsetDir}" -o "${icnsPath}"`, (error, stdout, stderr) => {
        if (error) {
          console.log(`   ⚠️  iconutil failed: ${error.message}`)
        } else {
          console.log('   ✓ icon.icns created successfully!')
        }
      })
    }
    
  } catch (error) {
    console.error('\n❌ Error generating icons:', error.message)
    process.exit(1)
  }
}

// Create default SVG if it doesn't exist
function createDefaultSvg() {
  const svgContent = `<?xml version="1.0" encoding="UTF-8"?>
<svg width="1024" height="1024" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a1a2e"/>
      <stop offset="50%" style="stop-color:#16213e"/>
      <stop offset="100%" style="stop-color:#0f0f23"/>
    </linearGradient>
    <linearGradient id="accentGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#ff6b6b"/>
      <stop offset="100%" style="stop-color:#ff8e53"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="20" flood-color="#000" flood-opacity="0.4"/>
    </filter>
  </defs>
  
  <!-- Background with rounded corners -->
  <rect x="0" y="0" width="1024" height="1024" rx="200" ry="200" fill="url(#bgGradient)"/>
  
  <!-- Decorative circles -->
  <circle cx="200" cy="200" r="300" fill="#ff6b6b" opacity="0.05"/>
  <circle cx="824" cy="824" r="400" fill="#ff8e53" opacity="0.05"/>
  
  <!-- Central letter K with gradient -->
  <g filter="url(#shadow)">
    <text x="512" y="680" 
          font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" 
          font-size="500" 
          font-weight="700" 
          fill="url(#accentGradient)" 
          text-anchor="middle">K</text>
  </g>
  
  <!-- Sound wave indicators -->
  <g stroke="url(#accentGradient)" stroke-width="24" stroke-linecap="round" fill="none" opacity="0.8">
    <path d="M 750 400 Q 800 512 750 624"/>
    <path d="M 820 340 Q 900 512 820 684"/>
    <path d="M 890 280 Q 1000 512 890 744" opacity="0.5"/>
  </g>
</svg>`
  
  ensureDir(iconsDir)
  fs.writeFileSync(svgPath, svgContent)
  console.log(`  ✓ Created default icon at ${svgPath}`)
}

main()
