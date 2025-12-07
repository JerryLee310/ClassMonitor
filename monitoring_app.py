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
                             QLabel, QPushButton, QFrame,
                             QDialog, QInputDialog, QMessageBox, QSystemTrayIcon, QMenu, QListWidget, QListWidgetItem,
                             QMenuBar, QAction, QSizePolicy, QActionGroup, QLineEdit, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QPoint, QSize
from PyQt5.QtGui import QImage, QPixmap, QFont, QIcon, QColor
try:
    from PyQt5.QtWinExtras import QtWin
except ImportError:
    pass

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

# Initialize TTS engine
try:
    tts_engine = pyttsx3.init()
    tts_engine.setProperty('rate', 150)
    tts_engine.setProperty('volume', 1.0)
except Exception as e:
    print(f"TTS engine initialization failed: {e}")
    tts_engine = None


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


class VideoListDialog(QDialog):
    """Dialog to display and manage video files"""
    
    def __init__(self, parent=None, encryption_manager=None):
        super().__init__(parent)
        self.encryption_manager = encryption_manager
        self.parent_app = parent
        self.setWindowTitle("视频列表")
        self.setMinimumSize(800, 500)
        self.setup_ui()
        self.load_videos()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = SubtitleLabel("加密视频列表")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0078D4;")
        layout.addWidget(title)
        
        # Video table
        self.video_table = QTableWidget()
        self.video_table.setColumnCount(4)
        self.video_table.setHorizontalHeaderLabels(["文件名", "大小", "修改时间", "操作"])
        self.video_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.video_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.video_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.video_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.video_table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1DFDD;
                border-radius: 8px;
                gridline-color: #E1DFDD;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #E6F4FF;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #F3F2F1;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #E1DFDD;
                font-weight: bold;
                color: #323130;
            }
        """)
        layout.addWidget(self.video_table)
        
        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        refresh_btn = PushButton(FluentIcon.SYNC, "刷新")
        refresh_btn.clicked.connect(self.load_videos)
        button_layout.addWidget(refresh_btn)
        
        close_btn = PrimaryPushButton(FluentIcon.CLOSE, "关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def load_videos(self):
        """Load video files from recordings directory"""
        self.video_table.setRowCount(0)
        
        if not os.path.exists(RECORDINGS_DIR):
            return
        
        video_files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.encrypted')]
        video_files.sort(key=lambda x: os.path.getmtime(os.path.join(RECORDINGS_DIR, x)), reverse=True)
        
        for filename in video_files:
            filepath = os.path.join(RECORDINGS_DIR, filename)
            file_size = os.path.getsize(filepath)
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
            
            row = self.video_table.rowCount()
            self.video_table.insertRow(row)
            
            # Filename
            name_item = QTableWidgetItem(filename)
            self.video_table.setItem(row, 0, name_item)
            
            # Size (convert to MB)
            size_mb = file_size / (1024 * 1024)
            size_item = QTableWidgetItem(f"{size_mb:.2f} MB")
            self.video_table.setItem(row, 1, size_item)
            
            # Modified time
            time_item = QTableWidgetItem(file_mtime.strftime("%Y-%m-%d %H:%M:%S"))
            self.video_table.setItem(row, 2, time_item)
            
            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 2, 5, 2)
            action_layout.setSpacing(5)
            
            export_btn = PushButton(FluentIcon.DOWNLOAD, "导出")
            export_btn.setFixedSize(80, 32)
            export_btn.clicked.connect(lambda checked, f=filename: self.export_video(f))
            action_layout.addWidget(export_btn)
            
            delete_btn = PushButton(FluentIcon.DELETE, "删除")
            delete_btn.setFixedSize(80, 32)
            delete_btn.clicked.connect(lambda checked, f=filename: self.delete_video(f))
            action_layout.addWidget(delete_btn)
            
            self.video_table.setCellWidget(row, 3, action_widget)
        
        if self.video_table.rowCount() == 0:
            self.video_table.insertRow(0)
            no_data_item = QTableWidgetItem("暂无视频文件")
            no_data_item.setForeground(QColor("#605E5C"))
            self.video_table.setItem(0, 0, no_data_item)
            self.video_table.setSpan(0, 0, 1, 4)
    
    def export_video(self, filename):
        """Export a video file"""
        try:
            encrypted_path = os.path.join(RECORDINGS_DIR, filename)
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            output_filename = filename.replace('.encrypted', '')
            output_path = os.path.join(desktop, output_filename)
            
            # Decrypt the video
            decrypted = self.encryption_manager.decrypt_file(encrypted_path, output_path)
            
            if decrypted:
                InfoBar.success(
                    title="成功",
                    content=f"视频已导出到桌面: {output_filename}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title="错误",
                    content="视频解密失败",
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
    
    def delete_video(self, filename):
        """Delete a video file with password protection"""
        # Verify password
        password_dialog = QDialog(self)
        password_dialog.setWindowTitle("密码验证")
        password_dialog.setFixedSize(350, 150)
        
        dialog_layout = QVBoxLayout(password_dialog)
        dialog_layout.setSpacing(15)
        dialog_layout.setContentsMargins(20, 20, 20, 20)
        
        label = BodyLabel("请输入密码以删除视频:")
        dialog_layout.addWidget(label)
        
        password_input = LineEdit()
        password_input.setEchoMode(QLineEdit.Password)
        password_input.setPlaceholderText("输入密码")
        dialog_layout.addWidget(password_input)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(password_dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        confirm_btn = PrimaryPushButton("确认")
        confirm_btn.clicked.connect(password_dialog.accept)
        button_layout.addWidget(confirm_btn)
        
        dialog_layout.addLayout(button_layout)
        
        if password_dialog.exec_() != QDialog.Accepted:
            return
        
        password = password_input.text()
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if password_hash != PASSWORD_HASH:
            InfoBar.error(
                title="错误",
                content="密码错误",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
        
        # Delete the file
        try:
            filepath = os.path.join(RECORDINGS_DIR, filename)
            os.remove(filepath)
            InfoBar.success(
                title="成功",
                content="视频已删除",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            self.load_videos()
        except Exception as e:
            InfoBar.error(
                title="错误",
                content=f"删除失败: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )


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
                    
                    # Use ASCII indicator to avoid garbled characters
                    cv2.circle(frame, (20, 20), 10, (0, 0, 255), -1)
                    cv2.putText(frame, "REC", (40, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
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
    """Global floating recorder window with edge-snapping"""
    
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.is_recording = False
        self.is_dragging = False
        self.drag_pos = None
        self.is_hidden_at_edge = False
        self.edge_threshold = 10  # Pixels from edge to trigger hiding
        self.hidden_size = 3  # Width/height when hidden
        self._force_close = False
        
        self.setup_ui()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set up timer to check edge proximity
        self.edge_timer = QTimer(self)
        self.edge_timer.timeout.connect(self.check_edge_proximity)
        self.edge_timer.start(100)
        
        self.normal_size = QSize(80, 240)
        self.resize(self.normal_size)
        self.move(100, 100)
        self.update_style()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title label
        self.title_label = QLabel()
        self.title_label.setPixmap(FluentIcon.HOME.pixmap(QSize(32, 32)))
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Open button
        self.open_btn = PushButton(FluentIcon.APPLICATION)
        self.open_btn.setFixedSize(60, 50)
        self.open_btn.setToolTip("打开主窗口")
        self.open_btn.clicked.connect(self.open_main_window)
        layout.addWidget(self.open_btn)
        
        # Record button
        self.record_btn = PushButton(FluentIcon.PLAY_SOLID)
        self.record_btn.setFixedSize(60, 50)
        self.record_btn.setToolTip("开始/停止录制")
        self.record_btn.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_btn)
        
        # Pen button
        self.pen_btn = PushButton(FluentIcon.EDIT)
        self.pen_btn.setFixedSize(60, 50)
        self.pen_btn.setToolTip("画笔工具")
        self.pen_btn.clicked.connect(self.launch_pen_tool)
        layout.addWidget(self.pen_btn)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def open_main_window(self):
        """Open main monitoring window"""
        self.parent_app.restore_window()
    
    def toggle_recording(self):
        """Toggle recording state"""
        self.parent_app.toggle_recording()
        self.set_recording_state(self.parent_app.recording)
    
    def set_recording_state(self, is_recording):
        """Update recording state"""
        self.is_recording = is_recording
        self.update_style()
    
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
    
    def update_style(self):
        """Update widget style based on recording state"""
        if self.is_recording:
            bg_color = "rgba(220, 38, 38, 220)"  # Red with transparency
            border_color = "#DC2626"
        else:
            bg_color = "rgba(30, 41, 59, 200)"  # Dark blue-gray with transparency
            border_color = "#1E293B"
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
            PushButton {{
                background-color: rgba(255, 255, 255, 30);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 8px;
                color: white;
                font-size: 18px;
            }}
            PushButton:hover {{
                background-color: rgba(255, 255, 255, 50);
            }}
            PushButton:pressed {{
                background-color: rgba(255, 255, 255, 70);
            }}
        """)
        
        # Update title icon
        if self.is_recording:
            self.title_label.setPixmap(FluentIcon.TRANSPARENT.pixmap(QSize(32, 32)))
        else:
            self.title_label.setPixmap(FluentIcon.HOME.pixmap(QSize(32, 32)))
        
        # Update record button icon
        if self.is_recording:
            self.record_btn.setIcon(FluentIcon.PAUSE.icon())
        else:
            self.record_btn.setIcon(FluentIcon.PLAY_SOLID.icon())
        self.record_btn.setToolTip("停止录制" if self.is_recording else "开始录制")
    
    def check_edge_proximity(self):
        """Check if widget is near screen edge and hide/show accordingly"""
        if self.is_dragging:
            return
        
        screen = QApplication.desktop().screenGeometry()
        pos = self.pos()
        
        # Check if near left or right edge
        near_left = pos.x() < self.edge_threshold
        near_right = pos.x() + self.width() > screen.width() - self.edge_threshold
        near_top = pos.y() < self.edge_threshold
        near_bottom = pos.y() + self.height() > screen.height() - self.edge_threshold
        
        if near_left or near_right or near_top or near_bottom:
            if not self.is_hidden_at_edge:
                self.hide_at_edge(near_left, near_right, near_top, near_bottom)
        else:
            if self.is_hidden_at_edge:
                self.show_from_edge()
    
    def hide_at_edge(self, left, right, top, bottom):
        """Hide widget at screen edge"""
        self.is_hidden_at_edge = True
        pos = self.pos()
        
        if left:
            self.setGeometry(-self.width() + self.hidden_size, pos.y(), self.width(), self.height())
        elif right:
            screen_width = QApplication.desktop().screenGeometry().width()
            self.setGeometry(screen_width - self.hidden_size, pos.y(), self.width(), self.height())
        elif top:
            self.setGeometry(pos.x(), -self.height() + self.hidden_size, self.width(), self.height())
        elif bottom:
            screen_height = QApplication.desktop().screenGeometry().height()
            self.setGeometry(pos.x(), screen_height - self.hidden_size, self.width(), self.height())
    
    def show_from_edge(self):
        """Show widget from edge"""
        self.is_hidden_at_edge = False
        # Widget will naturally move away from edge as user drags it
    
    def enterEvent(self, event):
        """Show full widget when mouse enters"""
        if self.is_hidden_at_edge:
            screen = QApplication.desktop().screenGeometry()
            pos = self.pos()
            
            # Determine which edge we're hidden at and show fully
            if pos.x() < 0:
                self.move(0, pos.y())
            elif pos.x() > screen.width() - self.width():
                self.move(screen.width() - self.width(), pos.y())
            elif pos.y() < 0:
                self.move(pos.x(), 0)
            elif pos.y() > screen.height() - self.height():
                self.move(pos.x(), screen.height() - self.height())
            
            self.is_hidden_at_edge = False
    
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
    
    def paintEvent(self, event):
        """Custom paint for better appearance"""
        super().paintEvent(event)
    
    def closeEvent(self, event):
        """Prevent closing unless forced"""
        if not self._force_close:
            event.ignore()
        else:
            super().closeEvent(event)

    def force_close(self):
        self._force_close = True
        self.close()


class VideoDisplayWidget(QWidget):
    """Keep the video preview constrained to a fixed aspect ratio"""
    def __init__(self, ratio=16/9, parent=None):
        super().__init__(parent)
        self.ratio = ratio
        self.setMinimumSize(960, 540)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label = QLabel("摄像头未启动", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #FFFFFF; font-size: 18px; background-color: #000000; border-radius: 12px;")
        self.current_pixmap = None
        self._update_geometry()
    
    def set_placeholder(self, text):
        self.current_pixmap = None
        self.label.setText(text)
        self.label.setPixmap(QPixmap())
        self.label.setStyleSheet("color: #FFFFFF; font-size: 18px; background-color: #000000; border-radius: 12px;")
    
    def set_frame(self, qt_image):
        self.current_pixmap = QPixmap.fromImage(qt_image)
        self.label.setText("")
        self._update_pixmap()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_geometry()
        self._update_pixmap()
    
    def _update_geometry(self):
        rect = self.contentsRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        width = rect.width()
        height = int(width / self.ratio)
        if height > rect.height():
            height = rect.height()
            width = int(height * self.ratio)
        x = rect.x() + (rect.width() - width) // 2
        y = rect.y() + (rect.height() - height) // 2
        self.label.setGeometry(x, y, width, height)
    
    def _update_pixmap(self):
        if not self.current_pixmap:
            return
        target_size = self.label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return
        scaled = self.current_pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(scaled)
    

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
        self.current_video_path = None
        self.start_camera_action = None
        self.stop_camera_action = None
        self.start_recording_action = None
        self.tray_record_action = None
        self.video_widget = None
        self.announcement_container_layout = None
        self.floating_widget = None
        
        self.load_config()
        self.setup_ui()
        self.setup_timer()
        self.setup_tray()
        self.cleanup_old_videos()
        self.protect_directories()
        
        atexit.register(self.on_exit)
    
    def setup_ui(self):
        self.setWindowTitle("智能监控系统")
        
        # Create menu bar
        menubar = self.menuBar()
        menubar.setStyleSheet(f"""
            QMenuBar {{
                background-color: {self.colors['surface']};
                color: {self.colors['text_primary']};
                font-family: 'Microsoft YaHei UI';
                padding: 5px;
            }}
            QMenuBar::item {{
                padding: 8px 12px;
                background: transparent;
            }}
            QMenuBar::item:selected {{
                background: {self.colors['hover']};
            }}
            QMenu {{
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
            }}
            QMenu::item {{
                padding: 8px 25px;
            }}
            QMenu::item:selected {{
                background-color: {self.colors['hover']};
            }}
        """)
        
        # Camera menu
        camera_menu = menubar.addMenu("摄像头")
        self.start_camera_action = QAction("启动摄像头", self)
        self.start_camera_action.triggered.connect(self.start_camera)
        camera_menu.addAction(self.start_camera_action)
        
        self.stop_camera_action = QAction("停止摄像头", self)
        self.stop_camera_action.triggered.connect(self.stop_camera)
        self.stop_camera_action.setEnabled(False)
        camera_menu.addAction(self.stop_camera_action)
        
        # Recording menu
        recording_menu = menubar.addMenu("录制")
        self.start_recording_action = QAction("开始录制", self)
        self.start_recording_action.triggered.connect(self.toggle_recording)
        self.start_recording_action.setEnabled(False)
        recording_menu.addAction(self.start_recording_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("设置")
        
        # Exposure submenu
        exposure_action = QAction("曝光调节", self)
        exposure_action.triggered.connect(self.show_exposure_dialog)
        settings_menu.addAction(exposure_action)
        
        # Time position submenu
        time_position_menu = settings_menu.addMenu("时间位置")
        position_group = QActionGroup(self)
        position_group.setExclusive(True)
        
        positions = [
            ("左上角", "top-left"),
            ("右上角", "top-right"),
            ("左下角", "bottom-left"),
            ("右下角", "bottom-right")
        ]
        
        for label, value in positions:
            action = QAction(label, self, checkable=True)
            action.setData(value)
            action.setChecked(value == self.time_position)
            action.triggered.connect(lambda checked, v=value: self.set_time_position(v))
            position_group.addAction(action)
            time_position_menu.addAction(action)
        
        # Video management menu
        video_menu = menubar.addMenu("视频管理")
        video_menu.addAction("视频列表", self.show_video_list)
        video_menu.addAction("导出视频", self.export_video)
        video_menu.addAction("删除视频", self.delete_video)
        
        # System menu
        system_menu = menubar.addMenu("系统")
        system_menu.addAction("退出程序", self.exit_program)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Left column: time bar and announcements
        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        
        # Time bar
        time_card = CardWidget()
        time_card.setFixedHeight(80)
        time_layout = QVBoxLayout(time_card)
        time_layout.setContentsMargins(20, 10, 20, 10)
        
        self.datetime_label = SubtitleLabel("")
        self.datetime_label.setStyleSheet(f"color: {self.colors['primary']}; font-weight: bold; font-size: 18px;")
        time_layout.addWidget(self.datetime_label, alignment=Qt.AlignCenter)
        
        self.status_label = CaptionLabel("状态: 空闲")
        self.status_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 12px;")
        time_layout.addWidget(self.status_label, alignment=Qt.AlignCenter)
        
        left_column.addWidget(time_card)
        
        # Announcements panel
        announcement_card = CardWidget()
        announcement_layout = QVBoxLayout(announcement_card)
        announcement_layout.setContentsMargins(15, 15, 15, 15)
        
        ann_header = QHBoxLayout()
        announcement_title = SubtitleLabel("通知公告")
        ann_header.addWidget(announcement_title)
        ann_header.addStretch()
        
        add_ann_btn = PushButton(FluentIcon.ADD)
        add_ann_btn.setFixedSize(32, 32)
        add_ann_btn.setToolTip("添加公告")
        add_ann_btn.clicked.connect(self.add_announcement)
        ann_header.addWidget(add_ann_btn)
        
        tts_ann_btn = PushButton(FluentIcon.MICROPHONE)
        tts_ann_btn.setFixedSize(32, 32)
        tts_ann_btn.setToolTip("朗读公告")
        tts_ann_btn.clicked.connect(self.tts_read_announcement)
        ann_header.addWidget(tts_ann_btn)
        
        clear_ann_btn = PushButton(FluentIcon.DELETE)
        clear_ann_btn.setFixedSize(32, 32)
        clear_ann_btn.setToolTip("清空所有公告")
        clear_ann_btn.clicked.connect(self.clear_announcements)
        ann_header.addWidget(clear_ann_btn)
        
        announcement_layout.addLayout(ann_header)
        
        # Announcement cards scroll area
        self.announcement_scroll = ScrollArea()
        self.announcement_scroll.setWidgetResizable(True)
        self.announcement_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.announcement_container = QWidget()
        self.announcement_container_layout = QVBoxLayout(self.announcement_container)
        self.announcement_container_layout.setSpacing(10)
        self.announcement_container_layout.setContentsMargins(0, 0, 0, 0)
        self.announcement_container_layout.addStretch()
        
        self.announcement_scroll.setWidget(self.announcement_container)
        announcement_layout.addWidget(self.announcement_scroll)
        
        left_column.addWidget(announcement_card, 1)
        
        main_layout.addLayout(left_column, 1)
        
        # Right side: Video display
        video_container = QVBoxLayout()
        video_container.setSpacing(0)
        
        self.video_widget = VideoDisplayWidget(16/9)
        video_container.addWidget(self.video_widget, 1)
        
        main_layout.addLayout(video_container, 2)
        
        self.update_announcement_display()
    
    def show_exposure_dialog(self):
        """Show exposure adjustment dialog"""
        value, ok = QInputDialog.getInt(
            self, "曝光调节", f"当前曝光值: {self.exposure}\n请输入新的曝光值 (-10 到 10):",
            int(self.exposure), -10, 10, 1
        )
        if ok:
            self.update_exposure(value)
            InfoBar.success(
                title="成功",
                content=f"曝光已设置为: {value}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
    
    def set_time_position(self, position):
        """Set time position from menu"""
        self.time_position = position
        if self.video_thread:
            self.video_thread.time_position = self.time_position
        self.save_config()
        InfoBar.success(
            title="成功",
            content=f"时间位置已更新",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
    
    def create_slide_menu(self):
        pass
    
    def show_slide_menu(self):
        pass
    
    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_datetime)
        self.timer.start(1000)
    
    def setup_tray(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Create tray menu
        tray_menu = QMenu()
        open_action = tray_menu.addAction("显示主界面")
        open_action.triggered.connect(self.restore_window)
        tray_menu.addSeparator()
        self.tray_record_action = tray_menu.addAction("开始录制")
        self.tray_record_action.triggered.connect(self.toggle_recording)
        tray_menu.addSeparator()
        exit_action = tray_menu.addAction("退出程序")
        exit_action.triggered.connect(self.exit_program)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Set tray icon - use FluentIcon
        tray_icon_pixmap = FluentIcon.VIDEO.pixmap(QSize(32, 32))
        self.tray_icon.setIcon(QIcon(tray_icon_pixmap))
        self.tray_icon.show()
    
    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_window()
    
    def restore_window(self):
        """Restore window from tray"""
        self.show()
        self.raise_()
        self.activateWindow()
        self.showFullScreen()
    
    def hide_to_tray(self, show_tip=True):
        """Hide the window and notify user via tray"""
        self.hide()
        if show_tip and self.tray_icon:
            self.tray_icon.showMessage(
                "智能监控系统",
                "程序已最小化到后台运行。",
                QSystemTrayIcon.Information,
                3000
            )
    
    def update_datetime(self):
        """Update datetime label"""
        now = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        self.datetime_label.setText(now)
    
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
        
        if tts_engine is None:
            InfoBar.error(
                title="错误",
                content="TTS引擎未初始化",
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
            tts_engine.say(text)
            tts_engine.runAndWait()
        except Exception as e:
            print(f"TTS error: {e}")
            InfoBar.error(
                title="错误",
                content=f"朗读失败: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
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
        """Update announcement display with cards"""
        # Clear existing widgets (except stretch)
        while self.announcement_container_layout.count() > 1:
            item = self.announcement_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.announcements:
            no_ann_label = BodyLabel("暂无公告")
            no_ann_label.setAlignment(Qt.AlignCenter)
            no_ann_label.setStyleSheet(f"color: {self.colors['text_secondary']}; padding: 20px;")
            self.announcement_container_layout.insertWidget(0, no_ann_label)
        else:
            for ann in self.announcements:
                ann_card = CardWidget()
                ann_card.setStyleSheet(f"""
                    CardWidget {{
                        background-color: {self.colors['surface']};
                        border: 1px solid {self.colors['border']};
                        border-radius: 8px;
                        padding: 10px;
                    }}
                """)
                ann_layout = QVBoxLayout(ann_card)
                ann_layout.setContentsMargins(12, 12, 12, 12)
                ann_layout.setSpacing(5)
                
                time_label = CaptionLabel(ann['timestamp'])
                time_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 10px;")
                ann_layout.addWidget(time_label)
                
                text_label = BodyLabel(ann['text'])
                text_label.setWordWrap(True)
                text_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 12px;")
                ann_layout.addWidget(text_label)
                
                self.announcement_container_layout.insertWidget(
                    self.announcement_container_layout.count() - 1, ann_card
                )
    
    def show_video_list(self):
        """Show video list dialog"""
        try:
            dialog = VideoListDialog(self, self.encryption_manager)
            dialog.exec_()
        except Exception as e:
            InfoBar.error(
                title="错误",
                content=f"无法打开视频列表: {str(e)}",
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
        password, ok = QInputDialog.getText(self, "删除视频", "请输入密码:", QLineEdit.Password)
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
        password, ok = QInputDialog.getText(self, "退出程序", "请输入密码:", QLineEdit.Password)
        if ok:
            if self.verify_password(password):
                self.on_exit()
                QApplication.quit()
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
            if self.start_camera_action:
                self.start_camera_action.setEnabled(False)
            if self.stop_camera_action:
                self.stop_camera_action.setEnabled(True)
            if self.start_recording_action:
                self.start_recording_action.setEnabled(True)
            self.status_label.setText("状态: 摄像头运行中")
            self.status_label.setStyleSheet(f"color: {self.colors['success']}; font-size: 12px;")
            if self.video_widget:
                self.video_widget.set_placeholder("")
            
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
        
        if self.start_camera_action:
            self.start_camera_action.setEnabled(True)
        if self.stop_camera_action:
            self.stop_camera_action.setEnabled(False)
        if self.start_recording_action:
            self.start_recording_action.setEnabled(False)
        if self.tray_record_action:
            self.tray_record_action.setText("开始录制")
        self.status_label.setText("状态: 空闲")
        self.status_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 12px;")
        if self.video_widget:
            self.video_widget.set_placeholder("摄像头已停止")
    
    def toggle_recording(self):
        """Toggle recording"""
        if self.cap is None:
            self.start_camera()
            if self.cap is None:
                InfoBar.warning(
                    title="提示",
                    content="摄像头未启动，无法录制",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return
        if not self.recording:
            if not os.path.exists(RECORDINGS_DIR):
                os.makedirs(RECORDINGS_DIR, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{RECORDINGS_DIR}/video_{timestamp}.avi"
            self.current_video_path = filename
            
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
            if self.start_recording_action:
                self.start_recording_action.setText("停止录制")
            if self.tray_record_action:
                self.tray_record_action.setText("停止录制")
            self.status_label.setText("状态: 正在录制")
            self.status_label.setStyleSheet(f"color: {self.colors['danger']}; font-size: 12px;")
            if self.floating_widget:
                self.floating_widget.set_recording_state(True)
        else:
            self.recording = False
            if self.video_thread:
                self.video_thread.recording = False
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
            
            # Encrypt the recorded video file
            if self.current_video_path and os.path.exists(self.current_video_path):
                self.encryption_manager.encrypt_file(self.current_video_path)
            self.current_video_path = None
            
            if self.start_recording_action:
                self.start_recording_action.setText("开始录制")
            if self.tray_record_action:
                self.tray_record_action.setText("开始录制")
            self.status_label.setText("状态: 摄像头运行中")
            self.status_label.setStyleSheet(f"color: {self.colors['success']}; font-size: 12px;")
            InfoBar.success(
                title="录制完成",
                content="视频已加密保存",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            if self.floating_widget:
                self.floating_widget.set_recording_state(False)

    
    @pyqtSlot(QImage)
    def update_video_frame(self, qt_image):
        """Update video frame"""
        if self.video_widget:
            self.video_widget.set_frame(qt_image)
    
    def protect_directories(self):
        """Protect software and recordings directories from Explorer access"""
        try:
            # Import windows_admin module
            try:
                import windows_admin
                if sys.platform == 'win32' and windows_admin.is_admin():
                    # Get program directory and recordings directory
                    prog_dir = os.path.dirname(os.path.abspath(__file__))
                    recordings_dir = os.path.abspath(RECORDINGS_DIR)
                    
                    # Protect both directories
                    directories = [prog_dir, recordings_dir]
                    result = windows_admin.protect_directories(directories)
                    
                    if result:
                        print("Directories protected successfully")
                    else:
                        print("Directory protection partially failed")
                else:
                    print("Not running as admin or not on Windows, skipping directory protection")
            except ImportError:
                print("windows_admin module not available, skipping directory protection")
        except Exception as e:
            print(f"Failed to protect directories: {e}")
    
    def on_exit(self):
        """Handle program exit"""
        self.stop_camera()
        self.save_config()
        if self.tray_icon:
            self.tray_icon.hide()
        if self.floating_widget:
            self.floating_widget.force_close()
    
    def closeEvent(self, event):
        """Handle close event - hide to tray instead of closing"""
        # Hide window to system tray, keep background process running
        self.hide_to_tray()
        event.ignore()

    def keyPressEvent(self, event):
        """Prevent exiting fullscreen via keyboard shortcuts"""
        if event.key() in (Qt.Key_Escape, Qt.Key_F11):
            event.ignore()
            self.showFullScreen()
        else:
            super().keyPressEvent(event)


def main():
    """Main entry point"""
    app = QApplication.instance() or QApplication(sys.argv)
    
    app.setApplicationName("智能监控系统")
    app.setOrganizationName("ClassMonitor")
    
    setTheme(Theme.LIGHT)
    
    window = MonitoringApp()
    
    # Create floating recorder widget
    floating_recorder = FloatingRecorderWidget(window)
    window.floating_widget = floating_recorder
    floating_recorder.show()
    
    window.showFullScreen()
    
    return app.exec_()


if __name__ == "__main__":
    main()
