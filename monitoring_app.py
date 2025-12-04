import cv2
import sys
import datetime
import threading
import json
import os
import time
import struct
import hashlib
import atexit
import ctypes
import subprocess
from pathlib import Path
from cryptography.fernet import Fernet
from PIL import Image, ImageQt
import pyttsx3

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QLabel, QPushButton, QFrame, QScrollArea, QTextEdit,
                             QDialog, QInputDialog, QMessageBox, QSystemTrayIcon, QMenu, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QPoint, QPropertyAnimation, QEasingCurve, QRect
from PyQt5.QtGui import QImage, QPixmap, QFont, QIcon, QColor
# Windows-specific import
try:
    from PyQt5.QtWinExtras import QtWin
except ImportError:
    # QtWin is only available on Windows
    QtWin = None

from qfluentwidgets import (
    FluentIcon, PushButton, PrimaryPushButton, InfoBar, InfoBarPosition, 
    CardWidget, SubtitleLabel, CaptionLabel, BodyLabel, StrongBodyLabel,
    Slider, ComboBox, ScrollArea, SmoothScrollArea, TextEdit, LineEdit,
    MessageBox, Dialog, FluentStyleSheet, setTheme, Theme, isDarkTheme,
    InfoBadge, ProgressRing, StateToolTip, ToolTipFilter
)

# Configuration constants
CONFIG_FILE = "config.json"
ENCRYPTION_KEY_FILE = ".key"
RECORDINGS_DIR = ".recordings"
BACKUP_DIR = ".recordings_backup"
PASSWORD_HASH = "1440717954315df5abbb85dce6f0f82e4c7d9f9990f53cdb4caf523e1001a730"  # SHA256 of "naxidatianxiadiyikeai1027"
RETENTION_DAYS = 7

# Initialize TTS engine (with error handling)
try:
    tts_engine = pyttsx3.init()
    tts_engine.setProperty('rate', 150)
    tts_engine.setProperty('volume', 1.0)
    TTS_AVAILABLE = True
except (RuntimeError, ImportError):
    # TTS not available (e.g., eSpeak not installed on Linux)
    tts_engine = None
    TTS_AVAILABLE = False


class EncryptionManager:
    """Handles encryption and decryption of video files"""
    
    def __init__(self):
        self.key_file = ENCRYPTION_KEY_FILE
        self.key = self._load_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _load_or_create_key(self):
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Hide the key file on Windows
            if sys.platform == 'win32':
                os.system(f'attrib +h "{self.key_file}"')
            return key
    
    def encrypt_file(self, input_path):
        """Encrypt a video file and save with .encrypted extension"""
        try:
            output_path = input_path + '.encrypted'
            with open(input_path, 'rb') as f:
                data = f.read()
            encrypted_data = self.cipher.encrypt(data)
            with open(output_path, 'wb') as f:
                f.write(encrypted_data)
            os.remove(input_path)
            return output_path
        except Exception as e:
            print(f"Encryption error: {e}")
            return None
    
    def decrypt_file(self, input_path, output_path=None):
        """Decrypt an encrypted video file"""
        try:
            if output_path is None:
                output_path = input_path.replace('.encrypted', '')
            with open(input_path, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)
            return output_path
        except Exception as e:
            print(f"Decryption error: {e}")
            return None


class VideoThread(QThread):
    frame_ready = pyqtSignal(QImage)
    status_changed = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.recording = False
        self.show_timestamp = True
        self.cap = None
        self.video_writer = None
        self.exposure = 0
        self.time_position = "top-right"
        
    def run(self):
        self.running = True
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                # Add timestamp only if we're recording and should show it
                if self.recording and self.show_timestamp:
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.7
                    font_thickness = 2
                    text_color = (255, 255, 255)
                    bg_color = (0, 0, 0)
                    
                    text_size = cv2.getTextSize(current_time, font, font_scale, font_thickness)[0]
                    text_width, text_height = text_size
                    padding = 10
                    
                    if self.time_position == "top-left":
                        x, y = padding, text_height + padding
                    elif self.time_position == "top-right":
                        x, y = frame.shape[1] - text_width - padding, text_height + padding
                    elif self.time_position == "bottom-left":
                        x, y = padding, frame.shape[0] - padding
                    elif self.time_position == "bottom-right":
                        x, y = frame.shape[1] - text_width - padding, frame.shape[0] - padding
                    else:
                        x, y = frame.shape[1] - text_width - padding, text_height + padding
                    
                    cv2.rectangle(frame, 
                                (x - 5, y - text_height - 5), 
                                (x + text_width + 5, y + 5), 
                                bg_color, -1)
                    cv2.putText(frame, current_time, (x, y), font, font_scale, text_color, font_thickness)
                
                if self.recording and self.video_writer is not None:
                    self.video_writer.write(frame)
                    
                    rec_text = "录制中"
                    rec_font_scale = 0.8
                    rec_thickness = 2
                    rec_color = (0, 0, 255)
                    cv2.putText(frame, rec_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, rec_font_scale, rec_color, rec_thickness)
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                self.frame_ready.emit(qt_image)
                
            self.msleep(50)
    
    def stop(self):
        self.running = False
        self.wait()


class FloatingRecorderWidget(QWidget):
    """Global floating recorder window"""
    
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.is_recording = False
        self.is_dragging = False
        self.drag_pos = None
        
        self.setup_ui()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setStyleSheet("""
            QWidget {
                background-color: #808080;
                border-radius: 5px;
            }
        """)
        self.resize(60, 200)
        self.move(100, 100)
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Open button
        self.open_btn = PushButton("打开")
        self.open_btn.clicked.connect(self.open_main_window)
        layout.addWidget(self.open_btn)
        
        # Record button
        self.record_btn = PushButton("录制")
        self.record_btn.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_btn)
        
        # Pen button
        self.pen_btn = PushButton("笔")
        self.pen_btn.clicked.connect(self.launch_pen_tool)
        layout.addWidget(self.pen_btn)
        
        self.setLayout(layout)
    
    def open_main_window(self):
        """Open main monitoring window"""
        self.parent_app.show()
        self.parent_app.raise_()
    
    def toggle_recording(self):
        """Toggle recording state"""
        if not self.is_recording:
            self.parent_app.start_camera()
            self.parent_app.toggle_recording()
            self.is_recording = True
            self.update_color()
        else:
            self.parent_app.toggle_recording()
            self.is_recording = False
            self.update_color()
    
    def launch_pen_tool(self):
        """Launch screen pen tool - placeholder for now"""
        InfoBar.info(
            title="提示",
            content="屏幕笔功能开发中",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
    
    def update_color(self):
        """Update widget color based on recording state"""
        if self.is_recording:
            color = "#FF0000"  # Red
        else:
            color = "#808080"  # Gray
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border-radius: 5px;
            }}
        """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        event.accept()


class MonitoringApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.colors = {
            'primary': '#0078D4',
            'secondary': '#605E5C',
            'accent': '#0078D4',
            'success': '#107C10',
            'warning': '#FF8C00',
            'danger': '#D13438',
            'background': '#F3F2F1',
            'surface': '#FFFFFF',
            'text_primary': '#323130',
            'text_secondary': '#605E5C',
            'border': '#E1DFDD',
            'hover': '#F3F2F1',
            'active': '#DEDEDE'
        }
        
        self.cap = None
        self.recording = False
        self.video_writer = None
        self.running = False
        self.exposure = 0
        self.time_position = "top-right"
        self.announcements = []
        self.config_file = CONFIG_FILE
        self.video_thread = None
        self.encryption_manager = EncryptionManager()
        self.menu_visible = False
        
        self.load_config()
        self.setup_ui()
        self.setup_timer()
        self.setup_tray()
        self.cleanup_old_videos()
        
        # Set window to stay on top
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        atexit.register(self.on_exit)
    
    def setup_ui(self):
        self.setWindowTitle("智能监控系统")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout (for slide menu)
        outer_layout = QHBoxLayout(central_widget)
        outer_layout.setSpacing(0)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        # Content container
        content_container = QWidget()
        main_layout = QGridLayout(content_container)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Top bar: Date/Time + Bell + Menu
        top_bar = QFrame()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(10, 5, 10, 5)
        
        # Date and time label
        self.datetime_label = BodyLabel("")
        self.datetime_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-weight: bold;")
        top_bar_layout.addWidget(self.datetime_label)
        
        top_bar_layout.addStretch()
        
        # Bell button
        self.bell_btn = PushButton("🔔")
        self.bell_btn.clicked.connect(self.play_bell_sound)
        self.bell_btn.setFixedSize(40, 40)
        top_bar_layout.addWidget(self.bell_btn)
        
        # Menu button
        self.menu_btn = PushButton("≡")
        self.menu_btn.clicked.connect(self.show_slide_menu)
        self.menu_btn.setFixedSize(40, 40)
        top_bar_layout.addWidget(self.menu_btn)
        
        main_layout.addWidget(top_bar, 0, 0, 1, 2)
        
        # Left side: Announcements
        announcement_card = CardWidget()
        announcement_layout = QVBoxLayout(announcement_card)
        
        announcement_title = SubtitleLabel("通知公告")
        announcement_layout.addWidget(announcement_title)
        
        # Announcement control buttons
        ann_btn_layout = QHBoxLayout()
        add_ann_btn = PrimaryPushButton("添加")
        add_ann_btn.clicked.connect(self.add_announcement)
        ann_btn_layout.addWidget(add_ann_btn)
        
        tts_ann_btn = PushButton("朗读")
        tts_ann_btn.clicked.connect(self.tts_read_announcement)
        ann_btn_layout.addWidget(tts_ann_btn)
        
        clear_ann_btn = PushButton("清空")
        clear_ann_btn.clicked.connect(self.clear_announcements)
        ann_btn_layout.addWidget(clear_ann_btn)
        
        announcement_layout.addLayout(ann_btn_layout)
        
        # Announcement text area
        self.announcement_text = QTextEdit()
        self.announcement_text.setReadOnly(True)
        self.announcement_text.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #323130;
                font-family: 'Microsoft YaHei UI';
                font-size: 10pt;
                border: 1px solid #E1DFDD;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        announcement_layout.addWidget(self.announcement_text)
        
        main_layout.addWidget(announcement_card, 1, 0)
        
        # Right side: Video
        video_card = CardWidget()
        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(10, 10, 10, 10)
        
        self.video_label = QLabel("摄像头未启动")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                color: #FFFFFF;
                font-family: 'Microsoft YaHei UI';
                font-size: 14px;
                border: none;
                min-height: 400px;
                min-width: 500px;
            }
        """)
        video_layout.addWidget(self.video_label)
        
        # Status bar
        self.status_label = BodyLabel("状态: 空闲")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {self.colors['primary']}; font-weight: bold;")
        video_layout.addWidget(self.status_label)
        
        # Control buttons
        control_btn_layout = QHBoxLayout()
        self.start_btn = PrimaryPushButton("启动摄像头")
        self.start_btn.clicked.connect(self.start_camera)
        control_btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = PushButton("停止摄像头")
        self.stop_btn.clicked.connect(self.stop_camera)
        self.stop_btn.setEnabled(False)
        control_btn_layout.addWidget(self.stop_btn)
        
        self.record_btn = PushButton("开始录制")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setEnabled(False)
        control_btn_layout.addWidget(self.record_btn)
        
        video_layout.addLayout(control_btn_layout)
        
        main_layout.addWidget(video_card, 1, 1)
        
        # Settings panel
        settings_card = CardWidget()
        settings_layout = QVBoxLayout(settings_card)
        
        settings_title = SubtitleLabel("设置")
        settings_layout.addWidget(settings_title)
        
        # Exposure setting
        exposure_layout = QHBoxLayout()
        exposure_label = BodyLabel("曝光:")
        exposure_layout.addWidget(exposure_label)
        
        self.exposure_scale = Slider(Qt.Horizontal)
        self.exposure_scale.setRange(-10, 10)
        self.exposure_scale.setValue(int(self.exposure))
        self.exposure_scale.valueChanged.connect(self.update_exposure)
        exposure_layout.addWidget(self.exposure_scale)
        
        self.exposure_value_label = QLabel(f"{self.exposure:.1f}")
        self.exposure_value_label.setFixedWidth(50)
        exposure_layout.addWidget(self.exposure_value_label)
        
        settings_layout.addLayout(exposure_layout)
        
        # Time position setting
        position_layout = QHBoxLayout()
        position_label = BodyLabel("时间位置:")
        position_layout.addWidget(position_label)
        
        self.position_combo = ComboBox()
        position_values = {
            "top-left": "左上角",
            "top-right": "右上角",
            "bottom-left": "左下角",
            "bottom-right": "右下角"
        }
        self.position_combo.addItems(list(position_values.values()))
        current_index = list(position_values.keys()).index(self.time_position) if self.time_position in position_values else 1
        self.position_combo.setCurrentIndex(current_index)
        self.position_combo.currentTextChanged.connect(self.update_time_position)
        position_layout.addWidget(self.position_combo)
        
        settings_layout.addLayout(position_layout)
        
        main_layout.addWidget(settings_card, 2, 0, 1, 2)
        
        # Add content container to outer layout
        outer_layout.addWidget(content_container, 1)
        
        # Create slide-out menu (initially hidden)
        self.slide_menu = self.create_slide_menu()
        outer_layout.addWidget(self.slide_menu, 0)
        
        self.update_announcement_display()
    
    def create_slide_menu(self):
        """Create the slide-out menu"""
        menu_widget = QFrame()
        menu_widget.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['surface']};
                border-left: 1px solid {self.colors['border']};
            }}
        """)
        menu_layout = QVBoxLayout(menu_widget)
        
        # Menu items
        menu_items = [
            ("📁 视频目录", self.open_videos_folder),
            ("📤 导出视频", self.export_video),
            ("🗑️ 删除视频", self.delete_video),
            ("🔐 密码设置", self.password_management),
            ("⚙️ 程序设置", self.program_settings),
            ("❌ 退出程序", self.exit_program),
        ]
        
        for label, callback in menu_items:
            btn = PushButton(label)
            btn.clicked.connect(callback)
            menu_layout.addWidget(btn)
        
        menu_layout.addStretch()
        
        menu_widget.setFixedWidth(200)
        menu_widget.hide()
        
        return menu_widget
    
    def show_slide_menu(self):
        """Show/hide the slide menu with animation"""
        if self.menu_visible:
            self.slide_menu.hide()
            self.menu_visible = False
        else:
            self.slide_menu.show()
            self.menu_visible = True
    
    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_datetime)
        self.timer.start(1000)
    
    def setup_tray(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Create tray menu
        tray_menu = QMenu()
        open_action = tray_menu.addAction("打开")
        open_action.triggered.connect(self.show)
        tray_menu.addSeparator()
        record_action = tray_menu.addAction("开始录制")
        record_action.triggered.connect(self.toggle_recording)
        tray_menu.addSeparator()
        exit_action = tray_menu.addAction("退出")
        exit_action.triggered.connect(self.exit_program)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Set tray icon
        self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_MediaPlay))
        self.tray_icon.show()
    
    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()
    
    def update_datetime(self):
        """Update datetime label"""
        now = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        self.datetime_label.setText(now)
    
    def play_bell_sound(self):
        """Play bell sound - will be implemented with audio file later"""
        InfoBar.success(
            title="铃铛",
            content="铃铛已按下",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
    
    def add_announcement(self):
        """Add new announcement with error handling"""
        try:
            text, ok = QInputDialog.getText(self, "添加公告", "请输入公告内容:")
            if ok and text.strip():
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.announcements.append({
                    'text': text.strip(),
                    'timestamp': timestamp
                })
                self.update_announcement_display()
                self.save_config()
                InfoBar.success(
                    title="成功",
                    content="公告添加成功",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
        except Exception as e:
            print(f"Error adding announcement: {e}")
            InfoBar.error(
                title="错误",
                content=f"添加公告失败: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def tts_read_announcement(self):
        """Read announcement using TTS"""
        if not self.announcements:
            InfoBar.warning(
                title="提示",
                content="没有公告可朗读",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # Get latest announcement
        latest = self.announcements[-1]
        text = latest['text']
        
        try:
            if TTS_AVAILABLE and tts_engine:
                tts_engine.say(text)
                tts_engine.runAndWait()
        except Exception as e:
            print(f"TTS error: {e}")
    
    def clear_announcements(self):
        """Clear all announcements"""
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有公告吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.announcements = []
            self.update_announcement_display()
            self.save_config()
    
    def update_announcement_display(self):
        """Update announcement display"""
        self.announcement_text.clear()
        if not self.announcements:
            self.announcement_text.append("暂无公告")
        else:
            for ann in self.announcements:
                text = f"[{ann['timestamp']}]\n{ann['text']}\n"
                self.announcement_text.append(text)
    
    def open_videos_folder(self):
        """Open videos folder"""
        try:
            if not os.path.exists(RECORDINGS_DIR):
                os.makedirs(RECORDINGS_DIR, exist_ok=True)
            
            folder_path = os.path.abspath(RECORDINGS_DIR)
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', folder_path])
                
            InfoBar.success(
                title="成功",
                content="视频文件夹已打开",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                title="错误",
                content=f"无法打开文件夹: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def export_video(self):
        """Export encrypted video to standard format"""
        try:
            if not os.path.exists(RECORDINGS_DIR):
                InfoBar.warning(
                    title="提示",
                    content="没有视频文件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return
            
            video_files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.encrypted')]
            if not video_files:
                InfoBar.warning(
                    title="提示",
                    content="没有视频文件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return
            
            # Select video to export
            export_dialog = QDialog(self)
            export_dialog.setWindowTitle("导出视频")
            layout = QVBoxLayout(export_dialog)
            
            list_widget = QListWidget()
            for video in video_files:
                list_widget.addItem(video)
            layout.addWidget(list_widget)
            
            btn_layout = QHBoxLayout()
            export_btn = PushButton("导出到桌面")
            cancel_btn = PushButton("取消")
            
            def do_export():
                items = list_widget.selectedItems()
                if not items:
                    InfoBar.warning(
                        title="提示",
                        content="请先选择视频",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                    return
                
                for item in items:
                    encrypted_path = os.path.join(RECORDINGS_DIR, item.text())
                    desktop = os.path.expanduser("~/Desktop")
                    output_path = os.path.join(desktop, item.text().replace('.encrypted', '.avi'))
                    
                    try:
                        decrypted = self.encryption_manager.decrypt_file(encrypted_path, output_path)
                        if decrypted:
                            InfoBar.success(
                                title="成功",
                                content=f"视频已导出到: {output_path}",
                                orient=Qt.Horizontal,
                                isClosable=True,
                                position=InfoBarPosition.TOP,
                                duration=3000,
                                parent=self
                            )
                    except Exception as e:
                        InfoBar.error(
                            title="错误",
                            content=f"导出失败: {str(e)}",
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP,
                            duration=3000,
                            parent=self
                        )
                
                export_dialog.accept()
            
            export_btn.clicked.connect(do_export)
            cancel_btn.clicked.connect(export_dialog.reject)
            
            btn_layout.addWidget(export_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)
            
            export_dialog.exec_()
        except Exception as e:
            InfoBar.error(
                title="错误",
                content=f"导出失败: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def delete_video(self):
        """Delete video with password protection"""
        password, ok = QInputDialog.getText(self, "删除视频", "请输入密码:", QInputDialog.PasswordInput)
        if ok and password:
            if self.verify_password(password):
                # List videos to delete
                if not os.path.exists(RECORDINGS_DIR):
                    InfoBar.warning(
                        title="提示",
                        content="没有视频文件",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                    return
                
                video_files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.encrypted')]
                if not video_files:
                    InfoBar.warning(
                        title="提示",
                        content="没有视频文件",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                    return
                
                # Show deletion dialog
                delete_dialog = QDialog(self)
                delete_dialog.setWindowTitle("删除视频")
                layout = QVBoxLayout(delete_dialog)
                
                list_widget = QListWidget()
                for video in video_files:
                    list_widget.addItem(video)
                layout.addWidget(list_widget)
                
                btn_layout = QHBoxLayout()
                delete_btn = PushButton("删除选中")
                cancel_btn = PushButton("取消")
                
                def do_delete():
                    for item in list_widget.selectedItems():
                        video_path = os.path.join(RECORDINGS_DIR, item.text())
                        try:
                            os.remove(video_path)
                        except Exception as e:
                            print(f"Delete error: {e}")
                    delete_dialog.accept()
                    InfoBar.success(
                        title="成功",
                        content="视频已删除",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                
                delete_btn.clicked.connect(do_delete)
                cancel_btn.clicked.connect(delete_dialog.reject)
                
                btn_layout.addWidget(delete_btn)
                btn_layout.addWidget(cancel_btn)
                layout.addLayout(btn_layout)
                
                delete_dialog.exec_()
            else:
                InfoBar.error(
                    title="错误",
                    content="密码错误",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
    
    def password_management(self):
        """Password management - show current password info"""
        InfoBar.info(
            title="密码管理",
            content="密码已锁定，无法更改",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def program_settings(self):
        """Program settings"""
        InfoBar.info(
            title="设置",
            content="程序设置功能开发中",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def verify_password(self, password):
        """Verify password"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        return password_hash == PASSWORD_HASH
    
    def exit_program(self):
        """Exit program with password protection"""
        password, ok = QInputDialog.getText(self, "退出程序", "请输入密码:", QInputDialog.PasswordInput)
        if ok:
            if self.verify_password(password):
                self.on_exit()
                sys.exit(0)
            else:
                InfoBar.error(
                    title="错误",
                    content="密码错误",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
    
    def cleanup_old_videos(self):
        """Delete videos older than RETENTION_DAYS"""
        try:
            if not os.path.exists(RECORDINGS_DIR):
                return
            
            now = time.time()
            for filename in os.listdir(RECORDINGS_DIR):
                filepath = os.path.join(RECORDINGS_DIR, filename)
                if os.path.isfile(filepath):
                    file_age = now - os.path.getctime(filepath)
                    if file_age > RETENTION_DAYS * 86400:  # Convert days to seconds
                        os.remove(filepath)
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.exposure = config.get('exposure', 0)
                    self.time_position = config.get('time_position', 'top-right')
                    self.announcements = config.get('announcements', [])
            except Exception as e:
                print(f"Error loading config: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        config = {
            'exposure': self.exposure,
            'time_position': self.time_position,
            'announcements': self.announcements
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def update_exposure(self, value):
        """Update exposure"""
        self.exposure = value
        self.exposure_value_label.setText(f"{self.exposure:.1f}")
        if self.cap is not None:
            try:
                self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            except:
                pass
        self.save_config()
    
    def update_time_position(self, text):
        """Update time position"""
        position_map = {
            "左上角": "top-left",
            "右上角": "top-right",
            "左下角": "bottom-left",
            "右下角": "bottom-right"
        }
        self.time_position = position_map.get(text, "top-right")
        if self.video_thread:
            self.video_thread.time_position = self.time_position
        self.save_config()
    
    def start_camera(self):
        """Start camera"""
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            
            if not self.cap.isOpened():
                InfoBar.error(
                    title="错误",
                    content="无法打开摄像头",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                self.cap = None
                return
            
            try:
                self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            except:
                pass
            
            self.running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.record_btn.setEnabled(True)
            self.status_label.setText("状态: 摄像头运行中")
            self.status_label.setStyleSheet(f"color: {self.colors['success']}; font-weight: bold;")
            self.video_label.setText("")
            
            # Start video thread
            self.video_thread = VideoThread()
            self.video_thread.cap = self.cap
            self.video_thread.exposure = self.exposure
            self.video_thread.time_position = self.time_position
            self.video_thread.frame_ready.connect(self.update_video_frame)
            self.video_thread.start()
    
    def stop_camera(self):
        """Stop camera"""
        if self.recording:
            self.toggle_recording()
        
        self.running = False
        
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread = None
        
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.record_btn.setEnabled(False)
        self.status_label.setText("状态: 空闲")
        self.status_label.setStyleSheet(f"color: {self.colors['primary']}; font-weight: bold;")
        self.video_label.setText("摄像头已停止")
        self.video_label.setPixmap(QPixmap())
    
    def toggle_recording(self):
        """Toggle recording"""
        if not self.recording:
            if not os.path.exists(RECORDINGS_DIR):
                os.makedirs(RECORDINGS_DIR, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{RECORDINGS_DIR}/video_{timestamp}.avi"
            
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            fps = 20.0
            frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.video_writer = cv2.VideoWriter(filename, fourcc, fps, (frame_width, frame_height))
            
            self.recording = True
            if self.video_thread:
                self.video_thread.recording = True
                self.video_thread.video_writer = self.video_writer
                self.video_thread.show_timestamp = True
            self.record_btn.setText("停止录制")
            self.status_label.setText("状态: 正在录制")
            self.status_label.setStyleSheet(f"color: {self.colors['danger']}; font-weight: bold;")
        else:
            self.recording = False
            if self.video_thread:
                self.video_thread.recording = False
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
            
            # Encrypt the video file
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = f"{RECORDINGS_DIR}/video_{timestamp}.avi"
            if os.path.exists(video_path):
                self.encryption_manager.encrypt_file(video_path)
            
            self.record_btn.setText("开始录制")
            self.status_label.setText("状态: 摄像头运行中")
            self.status_label.setStyleSheet(f"color: {self.colors['success']}; font-weight: bold;")
            InfoBar.success(
                title="录制完成",
                content="视频已加密保存",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    @pyqtSlot(QImage)
    def update_video_frame(self, qt_image):
        """Update video frame"""
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)
    
    def on_exit(self):
        """Handle program exit"""
        self.stop_camera()
        self.save_config()
        if self.tray_icon:
            self.tray_icon.hide()
    
    def closeEvent(self, event):
        """Handle close event"""
        # Ask for confirmation with password
        reply = QMessageBox.question(
            self, "退出程序", "确定要退出程序吗？需要密码确认。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            password, ok = QInputDialog.getText(self, "退出程序", "请输入密码:", QInputDialog.PasswordInput)
            if ok:
                if self.verify_password(password):
                    self.on_exit()
                    event.accept()
                else:
                    InfoBar.error(
                        title="错误",
                        content="密码错误，退出失败",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                    event.ignore()
            else:
                event.ignore()
        else:
            event.ignore()


def main():
    """Main entry point"""
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        
        app.setApplicationName("智能监控系统")
        app.setOrganizationName("ClassMonitor")
        
        setTheme(Theme.LIGHT)
        
        window = MonitoringApp()
        
        # Create floating recorder widget
        floating_recorder = FloatingRecorderWidget(window)
        floating_recorder.show()
        
        window.show()
        
        sys.exit(app.exec_())
    except Exception as e:
        if "platform plugin" in str(e) or "Could not load the Qt platform plugin" in str(e):
            print("图形界面初始化失败。这可能是因为：")
            print("1. 在无图形界面的环境中运行")
            print("2. 缺少必要的图形库")
            print("请在支持图形界面的环境中运行此程序。")
            print("\n如果您在 Windows 或 macOS 上运行，请直接双击运行。")
            print("如果您在 Linux 上运行，请确保已安装 X11 或 Wayland。")
        else:
            print(f"程序启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
