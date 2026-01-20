# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ILGC Workplace Monitor - macOS
========================================================

To build:
    pyinstaller ilgc_macos.spec

This will create a single executable in the dist/ folder.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get the project root directory
project_root = os.path.dirname(os.path.abspath(SPEC))

# Collect all hidden imports from requirements
hidden_imports = [
    # Flask and web
    'flask',
    'flask_cors',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.debug',
    'jinja2',
    'markupsafe',
    'click',
    'itsdangerous',
    'blinker',
    
    # HTTP and networking
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    
    # Scientific/numerical
    'numpy',
    'numpy.core',
    'numpy.core._methods',
    'numpy.lib.format',
    
    # Computer vision
    'cv2',
    'mss',
    'mss.darwin',
    
    # Bluetooth
    'bleak',
    'bleak.backends.corebluetooth',
    
    # LSL streaming
    'pylsl',
    
    # Notifications
    'plyer',
    'plyer.platforms.macosx',
    'plyer.platforms.macosx.notification',
    
    # Utilities
    'dotenv',
    'python_dotenv',
    'sympy',
    'mpmath',
    'typing_extensions',
    
    # Standard library
    'json',
    'logging',
    'threading',
    'subprocess',
    'signal',
    'webbrowser',
    'http.server',
    'functools',
    'pathlib',
    'datetime',
    'time',
    'os',
    'sys',
    're',
    'collections',
    'asyncio',
]

# Collect submodules for complex packages
hidden_imports += collect_submodules('bleak')
hidden_imports += collect_submodules('numpy')
hidden_imports += collect_submodules('cv2')
hidden_imports += collect_submodules('plyer')

# Data files to include (macOS uses colon as separator)
datas = [
    # macOS-specific files
    (os.path.join(project_root, 'mac', 'api_server.py'), 'mac'),
    (os.path.join(project_root, 'mac', 'src'), os.path.join('mac', 'src')),
    (os.path.join(project_root, 'mac', 'requirements.txt'), 'mac'),
    
    # pylsl library files (critical for macOS)
    (os.path.join(project_root, 'mac', 'lib', 'pylsl'), os.path.join('mac', 'lib', 'pylsl')),
    
    # Details and interventions templates
    (os.path.join(project_root, 'mac', 'details'), os.path.join('mac', 'details')),
]

# Add frontend dist only if it exists
frontend_dist = os.path.join(project_root, 'mac', 'frontend', 'dist')
if os.path.exists(frontend_dist):
    datas.append((frontend_dist, os.path.join('mac', 'frontend', 'dist')))

# Binary files - include dylibs for pylsl
binaries = [
    (os.path.join(project_root, 'mac', 'lib', 'pylsl', 'liblsl.dylib'), os.path.join('mac', 'lib', 'pylsl')),
    (os.path.join(project_root, 'mac', 'lib', 'pylsl', 'liblsl.2.dylib'), os.path.join('mac', 'lib', 'pylsl')),
    (os.path.join(project_root, 'mac', 'lib', 'pylsl', 'liblsl.1.16.2.dylib'), os.path.join('mac', 'lib', 'pylsl')),
]

# Filter out non-existent binary files
binaries = [(src, dst) for src, dst in binaries if os.path.exists(src)]

# Analysis
a = Analysis(
    [os.path.join(project_root, 'launcher.py')],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate entries
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create single executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ILGC-Workplace',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowed mode (no console)
    disable_windowed_traceback=False,
    argv_emulation=True,  # macOS-specific
    target_arch=None,
    codesign_identity=None,
    entitlements_file=os.path.join(project_root, 'resources', 'entitlements.plist') if os.path.exists(os.path.join(project_root, 'resources', 'entitlements.plist')) else None,
    icon=os.path.join(project_root, 'resources', 'icon.icns') if os.path.exists(os.path.join(project_root, 'resources', 'icon.icns')) else None,
)

# Create macOS .app bundle
app = BUNDLE(
    exe,
    name='ILGC-Workplace.app',
    icon=os.path.join(project_root, 'resources', 'icon.icns') if os.path.exists(os.path.join(project_root, 'resources', 'icon.icns')) else None,
    bundle_identifier='com.ilgc.workplace-monitor',
    info_plist={
        'CFBundleName': 'ILGC Workplace Monitor',
        'CFBundleDisplayName': 'ILGC Workplace Monitor',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSCameraUsageDescription': 'ILGC Workplace Monitor needs camera access to detect user presence and engagement.',
        'NSMicrophoneUsageDescription': 'ILGC Workplace Monitor may use the microphone for audio features.',
        'NSBluetoothAlwaysUsageDescription': 'ILGC Workplace Monitor needs Bluetooth access to connect to the heart rate monitor.',
        'NSBluetoothPeripheralUsageDescription': 'ILGC Workplace Monitor needs Bluetooth access to connect to the heart rate monitor.',
        'LSMinimumSystemVersion': '10.15',
    },
)
