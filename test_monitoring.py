import unittest
import os
import json
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from monitoring_app import MonitoringApp


class TestMonitoringApp(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = MonitoringApp(self.root)
        
    def tearDown(self):
        if os.path.exists('config.json'):
            os.remove('config.json')
        self.root.destroy()
        
    def test_initial_state(self):
        self.assertFalse(self.app.recording)
        self.assertIsNone(self.app.cap)
        self.assertEqual(self.app.exposure, 0)
        self.assertEqual(self.app.time_position, "top-right")
        self.assertEqual(self.app.announcements, [])
        
    def test_add_announcement(self):
        with patch('tkinter.simpledialog.askstring', return_value='Test announcement'):
            self.app.add_announcement()
            
        self.assertEqual(len(self.app.announcements), 1)
        self.assertEqual(self.app.announcements[0]['text'], 'Test announcement')
        self.assertIn('timestamp', self.app.announcements[0])
        
    def test_clear_announcements(self):
        self.app.announcements = [
            {'text': 'Test 1', 'timestamp': '2024-01-01 10:00:00'},
            {'text': 'Test 2', 'timestamp': '2024-01-01 11:00:00'}
        ]
        
        with patch('tkinter.messagebox.askyesno', return_value=True):
            self.app.clear_announcements()
            
        self.assertEqual(len(self.app.announcements), 0)
        
    def test_save_and_load_config(self):
        self.app.exposure = 5.0
        self.app.time_position = "bottom-left"
        self.app.announcements = [
            {'text': 'Test announcement', 'timestamp': '2024-01-01 10:00:00'}
        ]
        
        self.app.save_config()
        
        self.assertTrue(os.path.exists('config.json'))
        
        new_root = tk.Tk()
        new_app = MonitoringApp(new_root)
        
        self.assertEqual(new_app.exposure, 5.0)
        self.assertEqual(new_app.time_position, "bottom-left")
        self.assertEqual(len(new_app.announcements), 1)
        self.assertEqual(new_app.announcements[0]['text'], 'Test announcement')
        
        new_root.destroy()
        
    def test_update_exposure(self):
        self.app.update_exposure("7.5")
        self.assertEqual(self.app.exposure, 7.5)
        
    def test_update_time_position(self):
        self.app.position_var.set("bottom-right")
        self.app.update_time_position()
        self.assertEqual(self.app.time_position, "bottom-right")


if __name__ == '__main__':
    unittest.main()
