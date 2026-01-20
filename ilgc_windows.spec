# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ILGC Workplace Monitor - Windows
==========================================================

To build:
    pyinstaller ilgc_windows.spec

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
    'mss.windows',
    
    # Bluetooth
    'bleak',
    'bleak.backends.winrt',
    
    # LSL streaming
    'pylsl',
    
    # Notifications
    'plyer',
    'plyer.platforms.win',
    'plyer.platforms.win.notification',
    
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
    'asyncio.windows_events',
]

# Collect submodules for complex packages
hidden_imports += collect_submodules('bleak')
hidden_imports += collect_submodules('numpy')
hidden_imports += collect_submodules('cv2')
hidden_imports += collect_submodules('plyer')

# Data files to include
datas = [
    # Windows-specific files
    (os.path.join(project_root, 'windows', 'api_server.py'), 'windows'),
    (os.path.join(project_root, 'windows', 'src'), os.path.join('windows', 'src')),
    (os.path.join(project_root, 'windows', 'requirements.txt'), 'windows'),
    
    # Frontend dist (pre-built)
    (os.path.join(project_root, 'windows', 'frontend', 'dist'), os.path.join('windows', 'frontend', 'dist')),
    
    # Details and interventions templates
    (os.path.join(project_root, 'windows', 'details'), os.path.join('windows', 'details')),
]

# Add frontend dist only if it exists
frontend_dist = os.path.join(project_root, 'windows', 'frontend', 'dist')
if os.path.exists(frontend_dist):
    datas.append((frontend_dist, os.path.join('windows', 'frontend', 'dist')))

# Binary files
binaries = []

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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'resources', 'icon.ico') if os.path.exists(os.path.join(project_root, 'resources', 'icon.ico')) else None,
    version=os.path.join(project_root, 'resources', 'version_info.txt') if os.path.exists(os.path.join(project_root, 'resources', 'version_info.txt')) else None,
)
