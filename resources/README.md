# Resources Directory

This directory contains application resources like icons and assets.

## Required Files

### Windows
- `icon.ico` - Windows application icon (256x256 recommended, multi-resolution)
- `version_info.txt` - Windows version information for the executable

### macOS
- `icon.icns` - macOS application icon (1024x1024 recommended)
- `entitlements.plist` - macOS entitlements for code signing

## Creating Icons

### From a PNG Image

**macOS (create .icns):**
```bash
# Create iconset directory
mkdir icon.iconset

# Create required sizes
sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png

# Create icns file
iconutil -c icns icon.iconset
```

**Windows (create .ico):**
Use an online converter or ImageMagick:
```bash
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

## Placeholder Icons

Until proper icons are created, the build scripts will work without them - the resulting
applications will just use system default icons.

To add icons:
1. Create your icon artwork (recommend 1024x1024 PNG)
2. Convert to .icns and .ico using the methods above
3. Place files in this directory
4. Rebuild the application
