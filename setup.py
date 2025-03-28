#!/usr/bin/env python3
"""
Setup script for building macOS app
Usage:
  python setup.py py2app
"""

from setuptools import setup

APP = ['macos_app.py']
DATA_FILES = [
    'templates',
    'static',
    'utils',
    'web_interface.py',
    'Dockerfile',
    'docker-compose.yml',
    'README.md',
]
OPTIONS = {
    'argv_emulation': True,
    'packages': ['flask', 'werkzeug', 'jinja2', 'psutil', 'requests'],
    'iconfile': 'static/img/app_icon.icns',
    'plist': {
        'CFBundleName': 'Universal Media Converter',
        'CFBundleDisplayName': 'Universal Media Converter',
        'CFBundleIdentifier': 'com.example.universalmediaconverter',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': 'MIT License',
        'NSHighResolutionCapable': True,
    }
}

setup(
    name='Universal Media Converter',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
) 