#!/usr/bin/env python3
"""
Simple test script to verify the PyQt5/qfluentwidgets monitoring app
without requiring a full GUI environment.
"""

import os
import sys
import json

# Set virtual display for testing
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

try:
    import cv2
    import PyQt5
    import qfluentwidgets
    from PyQt5.QtWidgets import QApplication
    # Create QApplication first
    app = QApplication(sys.argv)
    from monitoring_app import MonitoringApp, VideoThread
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

def test_basic_functionality():
    """Test basic functionality without GUI"""
    print("\n=== Testing Basic Functionality ===")
    
    # Test VideoThread creation
    try:
        thread = VideoThread()
        assert not thread.running
        assert not thread.recording
        assert thread.cap is None
        assert thread.video_writer is None
        print("✓ VideoThread creation successful")
    except Exception as e:
        print(f"✗ VideoThread creation failed: {e}")
        return False
    
    # Test MonitoringApp creation (without showing)
    try:
        # Ensure QApplication exists
        from PyQt5.QtWidgets import QApplication
        if not QApplication.instance():
            test_app = QApplication(sys.argv)
        
        app = MonitoringApp()
        assert app.exposure == 0
        assert app.time_position == "top-right"
        assert app.announcements == []
        assert app.buttons_visible == True
        print("✓ MonitoringApp creation successful")
        
        # Test config operations
        app.exposure = 5.0
        app.time_position = "bottom-left"
        app.announcements = [{'text': 'Test', 'timestamp': '2024-01-01 10:00:00'}]
        app.save_config()
        print("✓ Config save successful")
        
        # Test config loading
        new_app = MonitoringApp()
        assert new_app.exposure == 5.0
        assert new_app.time_position == "bottom-left"
        assert len(new_app.announcements) == 1
        print("✓ Config load successful")
        
        # Test announcement display
        new_app.update_announcement_display()
        print("✓ Announcement display update successful")
        
        # Test exposure update
        new_app.update_exposure(7.5)
        assert new_app.exposure == 7.5
        print("✓ Exposure update successful")
        
        # Test position update
        new_app.update_time_position("右下角")
        assert new_app.time_position == "bottom-right"
        print("✓ Position update successful")
        
        # Test button visibility toggle
        new_app.toggle_buttons_visibility()
        assert not new_app.buttons_visible
        assert new_app.toggle_btn.text() == "显示控件"
        new_app.toggle_buttons_visibility()
        assert new_app.buttons_visible
        assert new_app.toggle_btn.text() == "隐藏控件"
        print("✓ Button visibility toggle successful")
        
        # Clean up
        new_app.close()
        app.close()
        
    except Exception as e:
        print(f"✗ MonitoringApp test failed: {e}")
        return False
    
    # Clean up test config
    if os.path.exists('config.json'):
        os.remove('config.json')
    
    return True

def test_dependencies():
    """Test that all required dependencies are available"""
    print("\n=== Testing Dependencies ===")
    
    try:
        import cv2
        print("✓ OpenCV available")
    except ImportError:
        print("✗ OpenCV not available")
        return False
    
    try:
        from PIL import Image, ImageQt
        print("✓ Pillow available")
    except ImportError:
        print("✗ Pillow not available")
        return False
    
    try:
        from PyQt5.QtWidgets import QApplication, QMainWindow
        from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
        from PyQt5.QtGui import QImage, QPixmap
        print("✓ PyQt5 available")
    except ImportError:
        print("✗ PyQt5 not available")
        return False
    
    try:
        from qfluentwidgets import (
            FluentIcon, PushButton, PrimaryPushButton, InfoBar, InfoBarPosition, 
            CardWidget, SubtitleLabel, BodyLabel, StrongBodyLabel,
            Slider, ComboBox, TextEdit, LineEdit,
            MessageBox, Dialog, FluentStyleSheet, setTheme, Theme
        )
        print("✓ qfluentwidgets available")
    except ImportError:
        print("✗ qfluentwidgets not available")
        return False
    
    return True

def main():
    """Main test function"""
    print("PyQt5/qfluentwidgets Monitoring App Test")
    print("=" * 50)
    
    # Test dependencies
    if not test_dependencies():
        print("\n✗ Dependency tests failed")
        return False
    
    # Test basic functionality
    if not test_basic_functionality():
        print("\n✗ Basic functionality tests failed")
        return False
    
    print("\n" + "=" * 50)
    print("✓ All tests passed successfully!")
    print("The PyQt5/qfluentwidgets monitoring app is working correctly.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)