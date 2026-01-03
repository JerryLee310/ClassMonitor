import os
import sys
import unittest
from unittest.mock import Mock, patch

from PyQt5.QtWidgets import QApplication, QMessageBox

from monitoring_app import MonitoringApp, VideoThread


class TestMonitoringApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.qt_app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        if os.path.exists('config.json'):
            os.remove('config.json')
        self.app_instance = MonitoringApp()

    def tearDown(self):
        try:
            self.app_instance.on_exit()
        except Exception:
            pass
        try:
            self.app_instance.deleteLater()
        except Exception:
            pass
        if os.path.exists('config.json'):
            os.remove('config.json')

    def test_initial_state(self):
        self.assertFalse(self.app_instance.recording)
        self.assertIsNone(self.app_instance.cap)
        self.assertEqual(self.app_instance.exposure, 0)
        self.assertEqual(self.app_instance.time_position, 'top-right')
        self.assertEqual(self.app_instance.timestamp_scale, 1.0)
        self.assertEqual(self.app_instance.record_indicator_scale, 1.0)
        self.assertEqual(self.app_instance.camera_index, 0)
        self.assertEqual(self.app_instance.announcements, [])

    def test_save_and_load_config(self):
        self.app_instance.exposure = 5
        self.app_instance.time_position = 'bottom-left'
        self.app_instance.timestamp_scale = 1.5
        self.app_instance.record_indicator_scale = 0.8
        self.app_instance.camera_index = 2
        self.app_instance.default_announcement_color = '#ff0000'
        self.app_instance.announcements = [
            {'text': 'Test announcement', 'timestamp': '2024-01-01 10:00:00', 'color': '#00ff00'}
        ]

        self.app_instance.save_config()
        self.assertTrue(os.path.exists('config.json'))

        new_instance = MonitoringApp()
        self.assertEqual(new_instance.exposure, 5)
        self.assertEqual(new_instance.time_position, 'bottom-left')
        self.assertAlmostEqual(new_instance.timestamp_scale, 1.5)
        self.assertAlmostEqual(new_instance.record_indicator_scale, 0.8)
        self.assertEqual(new_instance.camera_index, 2)
        self.assertEqual(new_instance.default_announcement_color, '#ff0000')
        self.assertEqual(len(new_instance.announcements), 1)
        self.assertEqual(new_instance.announcements[0]['text'], 'Test announcement')
        self.assertEqual(new_instance.announcements[0]['color'], '#00ff00')

        new_instance.on_exit()
        new_instance.deleteLater()

    def test_update_announcement_display_empty(self):
        self.app_instance.announcements = []
        self.app_instance.update_announcement_display()
        first_item = self.app_instance.announcement_container_layout.itemAt(0)
        self.assertIsNotNone(first_item)
        widget = first_item.widget()
        self.assertIsNotNone(widget)
        self.assertIn('暂无公告', widget.text())

    def test_update_announcement_display_with_items(self):
        self.app_instance.announcements = [
            {'text': 'Test 1', 'timestamp': '2024-01-01 10:00:00', 'color': '#123456'},
            {'text': 'Test 2', 'timestamp': '2024-01-01 11:00:00', 'color': '#654321'}
        ]
        self.app_instance.update_announcement_display()

        # First widget should be a card
        first_item = self.app_instance.announcement_container_layout.itemAt(0)
        card = first_item.widget()
        self.assertIsNotNone(card)
        labels = [w for w in card.findChildren(type(self.app_instance.datetime_label))]
        # labels may not include BodyLabel; just check any QLabel child texts
        texts = [w.text() for w in card.findChildren(type(self.app_instance.status_label))] + [w.text() for w in card.findChildren(type(self.app_instance.datetime_label))]
        # Fallback: look for QLabel children
        from PyQt5.QtWidgets import QLabel
        texts = [w.text() for w in card.findChildren(QLabel)]
        self.assertTrue(any('Test 1' in t for t in texts))

    @patch('cv2.VideoCapture')
    def test_start_camera_failure(self, mock_cv2):
        mock_cap = Mock()
        mock_cap.isOpened.return_value = False
        mock_cv2.return_value = mock_cap

        self.app_instance.camera_index = 1
        self.app_instance.start_camera()

        self.assertIsNone(self.app_instance.cap)
        self.assertFalse(self.app_instance.running)

    @patch('cv2.VideoCapture')
    def test_start_camera_success(self, mock_cv2):
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cv2.return_value = mock_cap

        with patch.object(VideoThread, 'start', return_value=None), patch.object(VideoThread, 'stop', return_value=None):
            self.app_instance.camera_index = 3
            self.app_instance.start_camera()

            mock_cv2.assert_called_with(3)
            self.assertIsNotNone(self.app_instance.cap)
            self.assertTrue(self.app_instance.running)
            self.assertFalse(self.app_instance.start_camera_action.isEnabled())
            self.assertTrue(self.app_instance.stop_camera_action.isEnabled())
            self.assertTrue(self.app_instance.start_recording_action.isEnabled())

            # cleanup within patched context
            self.app_instance.stop_camera()

    def test_clear_announcements(self):
        self.app_instance.announcements = [
            {'text': 'Test 1', 'timestamp': '2024-01-01 10:00:00', 'color': '#000000'}
        ]

        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            self.app_instance.clear_announcements()

        self.assertEqual(self.app_instance.announcements, [])


class TestVideoThread(unittest.TestCase):
    def test_video_thread_defaults(self):
        thread = VideoThread()
        self.assertFalse(thread.running)
        self.assertFalse(thread.recording)
        self.assertIsNone(thread.cap)
        self.assertIsNone(thread.video_writer)
        self.assertEqual(thread.exposure, 0)
        self.assertEqual(thread.time_position, 'top-right')
        self.assertEqual(thread.timestamp_scale, 1.0)
        self.assertEqual(thread.record_indicator_scale, 1.0)


if __name__ == '__main__':
    unittest.main()
