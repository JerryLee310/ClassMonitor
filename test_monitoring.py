import unittest
import os
import json
import sys
from unittest.mock import Mock, patch, MagicMock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
import cv2

# Import the new PyQt5 version
from monitoring_app import MonitoringApp, VideoThread


class TestMonitoringApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set virtual display for testing
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        # Create QApplication if it doesn't exist
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        self.app_instance = MonitoringApp()
        
    def tearDown(self):
        if os.path.exists('config.json'):
            os.remove('config.json')
        self.app_instance.close()
        
    def test_initial_state(self):
        self.assertFalse(self.app_instance.recording)
        self.assertIsNone(self.app_instance.cap)
        self.assertEqual(self.app_instance.exposure, 0)
        self.assertEqual(self.app_instance.time_position, "top-right")
        self.assertEqual(self.app_instance.announcements, [])
        self.assertTrue(self.app_instance.buttons_visible)
        
    def test_add_announcement(self):
        # Simulate adding an announcement directly
        timestamp = "2024-01-01 10:00:00"
        self.app_instance.announcements.append({
            'text': 'Test announcement',
            'timestamp': timestamp
        })
            
        self.assertEqual(len(self.app_instance.announcements), 1)
        self.assertEqual(self.app_instance.announcements[0]['text'], 'Test announcement')
        self.assertIn('timestamp', self.app_instance.announcements[0])
        
    def test_clear_announcements(self):
        self.app_instance.announcements = [
            {'text': 'Test 1', 'timestamp': '2024-01-01 10:00:00'},
            {'text': 'Test 2', 'timestamp': '2024-01-01 11:00:00'}
        ]
        
        # Mock the message box to return True (user confirms)
        with patch('qfluentwidgets.MessageBox.exec', return_value=True):
            self.app_instance.clear_announcements()
            
        self.assertEqual(len(self.app_instance.announcements), 0)
        
    def test_save_and_load_config(self):
        self.app_instance.exposure = 5.0
        self.app_instance.time_position = "bottom-left"
        self.app_instance.announcements = [
            {'text': 'Test announcement', 'timestamp': '2024-01-01 10:00:00'}
        ]
        
        self.app_instance.save_config()
        
        self.assertTrue(os.path.exists('config.json'))
        
        # Create a new app instance to test loading
        new_app_instance = MonitoringApp()
        
        self.assertEqual(new_app_instance.exposure, 5.0)
        self.assertEqual(new_app_instance.time_position, "bottom-left")
        self.assertEqual(len(new_app_instance.announcements), 1)
        self.assertEqual(new_app_instance.announcements[0]['text'], 'Test announcement')
        
        new_app_instance.close()
        
    def test_update_exposure(self):
        self.app_instance.update_exposure(7.5)
        self.assertEqual(self.app_instance.exposure, 7.5)
        
    def test_update_time_position(self):
        # Test the position update with Chinese text
        self.app_instance.update_time_position("右下角")
        self.assertEqual(self.app_instance.time_position, "bottom-right")
        
        self.app_instance.update_time_position("左上角")
        self.assertEqual(self.app_instance.time_position, "top-left")
        
    def test_toggle_buttons_visibility(self):
        # Initially buttons should be visible
        self.assertTrue(self.app_instance.buttons_visible)
        
        # Toggle to hide
        self.app_instance.toggle_buttons_visibility()
        self.assertFalse(self.app_instance.buttons_visible)
        self.assertEqual(self.app_instance.toggle_btn.text(), "显示控件")
        
        # Toggle to show
        self.app_instance.toggle_buttons_visibility()
        self.assertTrue(self.app_instance.buttons_visible)
        self.assertEqual(self.app_instance.toggle_btn.text(), "隐藏控件")
        
    def test_video_thread_creation(self):
        """Test that VideoThread can be created and has correct attributes"""
        thread = VideoThread()
        self.assertFalse(thread.running)
        self.assertFalse(thread.recording)
        self.assertIsNone(thread.cap)
        self.assertIsNone(thread.video_writer)
        self.assertEqual(thread.exposure, 0)
        self.assertEqual(thread.time_position, "top-right")
        
    @patch('cv2.VideoCapture')
    def test_start_camera_success(self, mock_cv2):
        """Test successful camera start"""
        # Mock the VideoCapture to return a successful open
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640  # Mock frame width
        # Mock read to return a valid frame
        mock_cap.read.return_value = (True, None)  # frame can be None for test
        mock_cv2.return_value = mock_cap
        
        # Start camera
        self.app_instance.start_camera()
        
        # Verify camera was initialized
        self.assertIsNotNone(self.app_instance.cap)
        self.assertTrue(self.app_instance.running)
        self.assertFalse(self.app_instance.start_btn.isEnabled())
        self.assertTrue(self.app_instance.stop_btn.isEnabled())
        self.assertTrue(self.app_instance.record_btn.isEnabled())
        
        # Clean up
        self.app_instance.stop_camera()
        
    @patch('cv2.VideoCapture')
    def test_start_camera_failure(self, mock_cv2):
        """Test camera start failure"""
        # Mock the VideoCapture to return failure
        mock_cap = Mock()
        mock_cap.isOpened.return_value = False
        mock_cv2.return_value = mock_cap
        
        # Start camera (should fail)
        self.app_instance.start_camera()
        
        # Verify camera was not initialized
        self.assertIsNone(self.app_instance.cap)
        self.assertFalse(self.app_instance.running)
        
    def test_update_announcement_display(self):
        """Test announcement display updates"""
        # Test with no announcements
        self.app_instance.announcements = []
        self.app_instance.update_announcement_display()
        self.assertIn("暂无公告", self.app_instance.announcement_text.toPlainText())
        
        # Test with announcements
        self.app_instance.announcements = [
            {'text': 'Test 1', 'timestamp': '2024-01-01 10:00:00'},
            {'text': 'Test 2', 'timestamp': '2024-01-01 11:00:00'}
        ]
        self.app_instance.update_announcement_display()
        display_text = self.app_instance.announcement_text.toPlainText()
        self.assertIn("[2024-01-01 10:00:00] Test 1", display_text)
        self.assertIn("[2024-01-01 11:00:00] Test 2", display_text)


class TestVideoThread(unittest.TestCase):
    def test_video_thread_creation(self):
        """Test VideoThread creation and initial state"""
        thread = VideoThread()
        self.assertFalse(thread.running)
        self.assertFalse(thread.recording)
        self.assertIsNone(thread.cap)
        self.assertIsNone(thread.video_writer)
        self.assertEqual(thread.exposure, 0)
        self.assertEqual(thread.time_position, "top-right")
        
    def test_video_thread_stop(self):
        """Test VideoThread stop method"""
        thread = VideoThread()
        # Mock the wait method to avoid actual waiting
        thread.wait = Mock()
        thread.running = True
        
        thread.stop()
        
        self.assertFalse(thread.running)
        thread.wait.assert_called_once()


if __name__ == '__main__':
    unittest.main()