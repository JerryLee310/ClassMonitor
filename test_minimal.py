#!/usr/bin/env python3
"""
Minimal test to check qfluentwidgets compatibility
"""

import os
import sys

# Set virtual display for testing
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

print("Testing qfluentwidgets import...")

try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
    print("✓ PyQt6 imported")
except Exception as e:
    print(f"✗ PyQt6 import failed: {e}")
    sys.exit(1)

try:
    from qfluentwidgets import (
        FluentIcon, PushButton, PrimaryPushButton, InfoBar, InfoBarPosition, 
        CardWidget, SubtitleLabel, BodyLabel, StrongBodyLabel,
        Slider, ComboBox, TextEdit, LineEdit,
        MessageBox, Dialog, FluentStyleSheet, setTheme, Theme
    )
    print("✓ qfluentwidgets imported")
except Exception as e:
    print(f"✗ qfluentwidgets import failed: {e}")
    sys.exit(1)

print("Creating QApplication...")
app = QApplication(sys.argv)

print("Creating simple widget...")
widget = QWidget()
print("✓ Widget created successfully")

print("Testing qfluentwidgets components...")

try:
    print("Testing PushButton...")
    button = PushButton("Test")
    print("✓ PushButton created")
except Exception as e:
    print(f"✗ PushButton failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("Testing CardWidget...")
    card = CardWidget()
    print("✓ CardWidget created")
except Exception as e:
    print(f"✗ CardWidget failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("Testing SubtitleLabel...")
    label = SubtitleLabel("Test")
    print("✓ SubtitleLabel created")
except Exception as e:
    print(f"✗ SubtitleLabel failed: {e}")
    import traceback
    traceback.print_exc()

print("All tests passed!")