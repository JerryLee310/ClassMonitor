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
import shutil
from pathlib import Path
from cryptography.fernet import Fernet
from PIL import Image, ImageQt
import pyttsx3

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
    QDialog, QInputDialog, QMessageBox, QSystemTrayIcon, QMenu, QListWidget, QListWidgetItem,
    QMenuBar, QAction, QSizePolicy, QActionGroup, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDateTimeEdit, QColorDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QPoint, QSize, QRect, QDateTime
from PyQt5.QtGui import QImage, QPixmap, QFont, QIcon, QColor, QCursor
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
        self.timestamp_scale = 1.0
        self.record_indicator_scale = 1.0
        
    def run(self):
        self.running = True
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                # Add timestamp only if we're recording and should show it
                if self.recording and self.show_timestamp:
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.7 * float(self.timestamp_scale)
                    font_thickness = max(1, int(round(2 * float(self.timestamp_scale))))
                    text_color = (255, 255, 255)
                    bg_color = (0, 0, 0)

                    text_size = cv2.getTextSize(current_time, font, font_scale, font_thickness)[0]
                    text_width, text_height = text_size
                    padding = max(6, int(round(10 * float(self.timestamp_scale))))

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

                    box_padding = max(4, int(round(5 * float(self.timestamp_scale))))
                    cv2.rectangle(
                        frame,
                        (x - box_padding, y - text_height - box_padding),
                        (x + text_width + box_padding, y + box_padding),
                        bg_color,
                        -1
                    )
                    cv2.putText(frame, current_time, (x, y), font, font_scale, text_color, font_thickness)

                if self.recording and self.video_writer is not None:
                    self.video_writer.write(frame)

                    scale = float(self.record_indicator_scale)
                    radius = max(6, int(round(10 * scale)))
                    circle_x = max(radius + 2, int(round(20 * scale)))
                    circle_y = max(radius + 2, int(round(20 * scale)))
                    text_x = circle_x + radius + max(6, int(round(10 * scale)))
                    text_y = circle_y + max(6, int(round(6 * scale)))
                    rec_font_scale = 0.7 * scale
                    rec_thickness = max(1, int(round(2 * scale)))

                    # Use ASCII indicator to avoid garbled characters
                    cv2.circle(frame, (circle_x, circle_y), radius, (0, 0, 255), -1)
                    cv2.putText(frame, "REC", (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, rec_font_scale, (0, 0, 255), rec_thickness)
                
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
        self.is_hovering = False
        self.hidden_edge = None
        self.edge_threshold = 12  # Pixels from edge to trigger hiding
        self.hidden_size = 16  # Width/height when hidden
        self.edge_hot_zone = 2  # Pixels from screen edge to trigger wake
        self.last_wake_time = 0.0
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
        self.title_label.setPixmap(FluentIcon.HOME.icon().pixmap(QSize(32, 32)))
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Open button
        self.open_btn = PushButton(FluentIcon.APPLICATION, "")
        self.open_btn.setFixedSize(60, 50)
        self.open_btn.setIconSize(QSize(26, 26))
        self.open_btn.setToolTip("打开主窗口")
        self.open_btn.clicked.connect(self.open_main_window)
        layout.addWidget(self.open_btn)
        
        # Record button
        self.record_btn = PushButton(FluentIcon.PLAY_SOLID, "")
        self.record_btn.setFixedSize(60, 50)
        self.record_btn.setIconSize(QSize(26, 26))
        self.record_btn.setToolTip("开始/停止录制")
        self.record_btn.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_btn)
        
        # Pen button
        self.pen_btn = PushButton(FluentIcon.EDIT, "")
        self.pen_btn.setFixedSize(60, 50)
        self.pen_btn.setIconSize(QSize(26, 26))
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
                padding: 0px;
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
            self.title_label.setPixmap(FluentIcon.TRANSPARENT.icon().pixmap(QSize(32, 32)))
        else:
            self.title_label.setPixmap(FluentIcon.HOME.icon().pixmap(QSize(32, 32)))
        
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

        if self.is_hidden_at_edge:
            if self.is_hovering:
                return

            cursor = QCursor.pos()
            if self._is_cursor_in_wake_zone(cursor, screen):
                self.unhide_from_edge()
            return

        # Avoid immediately hiding again right after waking up
        if time.time() - self.last_wake_time < 0.8:
            return

        if self.is_hovering:
            return

        # Check if near screen edge
        near_left = pos.x() <= self.edge_threshold
        near_right = pos.x() + self.width() >= screen.width() - self.edge_threshold
        near_top = pos.y() <= self.edge_threshold
        near_bottom = pos.y() + self.height() >= screen.height() - self.edge_threshold

        if near_left or near_right or near_top or near_bottom:
            self.hide_at_edge(near_left, near_right, near_top, near_bottom)

    def _is_cursor_in_wake_zone(self, cursor_pos: QPoint, screen: QRect) -> bool:
        if not self.hidden_edge:
            return False

        x = cursor_pos.x()
        y = cursor_pos.y()
        left = screen.left()
        right = screen.right()
        top = screen.top()
        bottom = screen.bottom()

        if self.hidden_edge == "left":
            return x <= left + self.edge_hot_zone and self.y() <= y <= self.y() + self.height()
        if self.hidden_edge == "right":
            return x >= right - self.edge_hot_zone and self.y() <= y <= self.y() + self.height()
        if self.hidden_edge == "top":
            return y <= top + self.edge_hot_zone and self.x() <= x <= self.x() + self.width()
        if self.hidden_edge == "bottom":
            return y >= bottom - self.edge_hot_zone and self.x() <= x <= self.x() + self.width()

        return False

    def hide_at_edge(self, left: bool, right: bool, top: bool, bottom: bool):
        """Hide widget at screen edge, leaving a small handle visible"""
        if self.is_hidden_at_edge:
            return

        self.is_hidden_at_edge = True
        pos = self.pos()

        if left:
            self.hidden_edge = "left"
            self.setGeometry(-self.width() + self.hidden_size, pos.y(), self.width(), self.height())
        elif right:
            self.hidden_edge = "right"
            screen_width = QApplication.desktop().screenGeometry().width()
            self.setGeometry(screen_width - self.hidden_size, pos.y(), self.width(), self.height())
        elif top:
            self.hidden_edge = "top"
            self.setGeometry(pos.x(), -self.height() + self.hidden_size, self.width(), self.height())
        elif bottom:
            self.hidden_edge = "bottom"
            screen_height = QApplication.desktop().screenGeometry().height()
            self.setGeometry(pos.x(), screen_height - self.hidden_size, self.width(), self.height())

    def unhide_from_edge(self):
        """Show widget fully when hidden at screen edge"""
        if not self.is_hidden_at_edge:
            return

        screen = QApplication.desktop().screenGeometry()
        pos = self.pos()

        if self.hidden_edge == "left":
            self.move(0, pos.y())
        elif self.hidden_edge == "right":
            self.move(screen.width() - self.width(), pos.y())
        elif self.hidden_edge == "top":
            self.move(pos.x(), 0)
        elif self.hidden_edge == "bottom":
            self.move(pos.x(), screen.height() - self.height())

        self.is_hidden_at_edge = False
        self.last_wake_time = time.time()

    def enterEvent(self, event):
        self.is_hovering = True
        if self.is_hidden_at_edge:
            self.unhide_from_edge()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovering = False
        super().leaveEvent(event)

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
        self.timestamp_scale = 1.0
        self.record_indicator_scale = 1.0
        self.camera_index = 0
        self.default_announcement_color = self.colors['text_primary']
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

        camera_menu.addSeparator()
        self.camera_select_menu = camera_menu.addMenu("选择录制摄像头")
        self.camera_select_menu.aboutToShow.connect(self.populate_camera_select_menu)

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

        settings_menu.addSeparator()
        overlay_menu = settings_menu.addMenu("叠加显示")
        overlay_menu.addAction("时间大小", self.change_timestamp_scale)
        overlay_menu.addAction("录制标识大小", self.change_record_indicator_scale)
        
        # Video management menu
        video_menu = menubar.addMenu("视频管理")
        video_menu.addAction("视频列表", self.show_video_list)
        video_menu.addAction("导出视频", self.export_video)
        video_menu.addAction("删除视频", self.delete_video)
        
        # System menu
        system_menu = menubar.addMenu("系统")
        system_menu.addAction("设置系统时间", self.show_set_system_time_dialog)
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
        
        add_ann_btn = PushButton(FluentIcon.ADD, "")
        self._setup_icon_only_button(add_ann_btn)
        add_ann_btn.setToolTip("添加公告")
        add_ann_btn.clicked.connect(self.add_announcement)
        ann_header.addWidget(add_ann_btn)

        color_ann_btn = PushButton(FluentIcon.PALETTE, "")
        self._setup_icon_only_button(color_ann_btn)
        color_ann_btn.setToolTip("公告默认颜色")
        color_ann_btn.clicked.connect(self.change_default_announcement_color)
        ann_header.addWidget(color_ann_btn)
        
        tts_ann_btn = PushButton(FluentIcon.MICROPHONE, "")
        self._setup_icon_only_button(tts_ann_btn)
        tts_ann_btn.setToolTip("朗读公告")
        tts_ann_btn.clicked.connect(self.tts_read_announcement)
        ann_header.addWidget(tts_ann_btn)
        
        clear_ann_btn = PushButton(FluentIcon.DELETE, "")
        self._setup_icon_only_button(clear_ann_btn)
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

    def _setup_icon_only_button(self, btn: PushButton, size: int = 32, icon_size=None):
        btn.setFixedSize(size, size)
        btn.setIconSize(icon_size if icon_size else QSize(16, 16))
        btn.setStyleSheet("PushButton { padding: 0px; }")

    def detect_available_cameras(self, max_index: int = 6):
        """Detect available camera indices."""
        available = []
        for idx in range(max_index):
            cap = None
            try:
                cap = cv2.VideoCapture(idx)
                if cap is not None and cap.isOpened():
                    available.append(idx)
            except Exception:
                pass
            finally:
                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass
        return available

    def populate_camera_select_menu(self):
        if not self.camera_select_menu:
            return

        self.camera_select_menu.clear()

        available = self.detect_available_cameras()
        if not available:
            available = [0]

        group = QActionGroup(self)
        group.setExclusive(True)

        for idx in available:
            action = QAction(f"摄像头 {idx}", self, checkable=True)
            action.setChecked(idx == self.camera_index)
            action.triggered.connect(lambda checked, i=idx: self.set_camera_index(i))
            group.addAction(action)
            self.camera_select_menu.addAction(action)

        self.camera_select_menu.addSeparator()
        manual_action = QAction("手动输入...", self)
        manual_action.triggered.connect(self.set_camera_index_manual)
        self.camera_select_menu.addAction(manual_action)

    def set_camera_index_manual(self):
        value, ok = QInputDialog.getInt(self, "选择摄像头", "请输入摄像头编号:", int(self.camera_index), 0, 20, 1)
        if ok:
            self.set_camera_index(value)

    def set_camera_index(self, idx: int):
        idx = int(idx)
        if idx == self.camera_index:
            return

        self.camera_index = idx
        self.save_config()

        if self.cap is not None:
            self.stop_camera()
            self.start_camera()

        InfoBar.success(
            title="成功",
            content=f"已选择摄像头: {idx}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def change_timestamp_scale(self):
        percent, ok = QInputDialog.getInt(
            self,
            "时间大小",
            "请输入时间大小百分比 (50 - 200):",
            int(round(self.timestamp_scale * 100)),
            50,
            200,
            5
        )
        if not ok:
            return

        self.timestamp_scale = percent / 100.0
        if self.video_thread:
            self.video_thread.timestamp_scale = self.timestamp_scale
        self.save_config()

    def change_record_indicator_scale(self):
        percent, ok = QInputDialog.getInt(
            self,
            "录制标识大小",
            "请输入录制标识大小百分比 (50 - 200):",
            int(round(self.record_indicator_scale * 100)),
            50,
            200,
            5
        )
        if not ok:
            return

        self.record_indicator_scale = percent / 100.0
        if self.video_thread:
            self.video_thread.record_indicator_scale = self.record_indicator_scale
        self.save_config()

    def change_default_announcement_color(self):
        color = QColorDialog.getColor(QColor(self.default_announcement_color), self, "选择公告默认颜色")
        if not color.isValid():
            return

        self.default_announcement_color = color.name()
        self.save_config()
        self.update_announcement_display()

    def show_set_system_time_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("设置系统时间")
        dialog.setFixedSize(420, 200)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        tip = BodyLabel("需要管理员权限。修改后会立即生效，精确到秒。")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        dt_edit = QDateTimeEdit(QDateTime.currentDateTime(), dialog)
        dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        dt_edit.setCalendarPopup(True)
        layout.addWidget(dt_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = PrimaryPushButton("应用")

        def apply_time():
            dt = dt_edit.dateTime().toPyDateTime()
            if self.set_system_time(dt):
                dialog.accept()

        ok_btn.clicked.connect(apply_time)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)
        dialog.exec_()

    def set_system_time(self, dt: datetime.datetime) -> bool:
        """Set system time. Returns True on success."""
        dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")

        try:
            if sys.platform == 'win32':
                try:
                    is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
                except Exception:
                    is_admin = False

                if not is_admin:
                    InfoBar.error(
                        title="错误",
                        content="需要管理员权限才能修改系统时间",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                    return False

                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", f'Set-Date -Date "{dt_str}"'],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise RuntimeError((result.stderr or result.stdout or "未知错误").strip())
            else:
                # Try timedatectl first (systemd), fallback to date
                if shutil.which('timedatectl'):
                    result = subprocess.run(
                        ["timedatectl", "set-time", dt_str],
                        capture_output=True,
                        text=True
                    )
                else:
                    result = subprocess.run(
                        ["date", "-s", dt_str],
                        capture_output=True,
                        text=True
                    )

                if result.returncode != 0:
                    raise RuntimeError((result.stderr or result.stdout or "权限不足或命令失败").strip())

            InfoBar.success(
                title="成功",
                content=f"系统时间已设置为: {dt_str}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            self.update_datetime()
            return True
        except Exception as e:
            InfoBar.error(
                title="错误",
                content=f"设置系统时间失败: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self
            )
            return False

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
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

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
        tray_qicon = FluentIcon.VIDEO.icon()
        self.tray_icon.setIcon(tray_qicon)
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
        """Add new announcement"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加公告")
        dialog.setMinimumSize(420, 260)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        label = BodyLabel("请输入公告内容:")
        layout.addWidget(label)

        text_edit = TextEdit()
        text_edit.setPlaceholderText("请输入公告内容...")
        layout.addWidget(text_edit)

        color_row = QHBoxLayout()
        color_row.setSpacing(10)
        color_row.addWidget(BodyLabel("文字颜色:"))

        selected = {'color': QColor(self.default_announcement_color)}
        color_preview = QFrame()
        color_preview.setFixedSize(22, 22)
        color_preview.setStyleSheet(
            f"background-color: {selected['color'].name()}; border: 1px solid {self.colors['border']}; border-radius: 4px;"
        )
        color_row.addWidget(color_preview)

        pick_btn = PushButton(FluentIcon.PALETTE, "选择")

        def pick_color():
            c = QColorDialog.getColor(selected['color'], dialog, "选择公告文字颜色")
            if c.isValid():
                selected['color'] = c
                color_preview.setStyleSheet(
                    f"background-color: {c.name()}; border: 1px solid {self.colors['border']}; border-radius: 4px;"
                )

        pick_btn.clicked.connect(pick_color)
        color_row.addWidget(pick_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = PrimaryPushButton("添加")

        def do_add():
            text = text_edit.toPlainText().strip()
            if not text:
                InfoBar.warning(
                    title="提示",
                    content="公告内容不能为空",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=dialog
                )
                return
            dialog.accept()

        ok_btn.clicked.connect(do_add)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        if dialog.exec_() != QDialog.Accepted:
            return

        try:
            text = text_edit.toPlainText().strip()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.announcements.append({
                'text': text,
                'timestamp': timestamp,
                'color': selected['color'].name()
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
    
    def verify_password_with_dialog(self, parent=None):
        """Verify password via dialog for protected operations"""
        dialog = QDialog(parent if parent else self)
        dialog.setWindowTitle("密码验证")
        dialog.setFixedSize(350, 150)
        
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setSpacing(15)
        dialog_layout.setContentsMargins(20, 20, 20, 20)
        
        label = BodyLabel("请输入密码:")
        dialog_layout.addWidget(label)
        
        password_input = LineEdit()
        password_input.setEchoMode(QLineEdit.Password)
        password_input.setPlaceholderText("输入密码")
        dialog_layout.addWidget(password_input)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        confirm_btn = PrimaryPushButton("确认")
        confirm_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(confirm_btn)
        
        dialog_layout.addLayout(button_layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return False
        
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
                parent=dialog
            )
            return False
        
        return True
    
    def tts_read_announcement(self):
        """Read announcement using TTS (password protected)"""
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
        
        # Verify password before TTS
        if not self.verify_password_with_dialog():
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
            for idx, ann in enumerate(self.announcements):
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
                ann_layout.setSpacing(6)

                header = QHBoxLayout()
                header.setContentsMargins(0, 0, 0, 0)
                header.setSpacing(6)

                time_label = CaptionLabel(ann.get('timestamp', ''))
                time_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 10px;")
                header.addWidget(time_label)
                header.addStretch()

                color_btn = PushButton(FluentIcon.PALETTE, "")
                self._setup_icon_only_button(color_btn, size=28, icon_size=QSize(14, 14))
                color_btn.setToolTip("修改颜色")
                color_btn.clicked.connect(lambda checked, i=idx: self.change_announcement_color(i))
                header.addWidget(color_btn)

                delete_btn = PushButton(FluentIcon.DELETE, "")
                self._setup_icon_only_button(delete_btn, size=28, icon_size=QSize(14, 14))
                delete_btn.setToolTip("删除")
                delete_btn.clicked.connect(lambda checked, i=idx: self.delete_announcement(i))
                header.addWidget(delete_btn)

                ann_layout.addLayout(header)

                color = ann.get('color', self.default_announcement_color)
                text_label = BodyLabel(ann.get('text', ''))
                text_label.setWordWrap(True)
                text_label.setStyleSheet(f"color: {color}; font-size: 12px;")
                ann_layout.addWidget(text_label)

                self.announcement_container_layout.insertWidget(
                    self.announcement_container_layout.count() - 1, ann_card
                )

    def change_announcement_color(self, index: int):
        if index < 0 or index >= len(self.announcements):
            return

        current = QColor(self.announcements[index].get('color', self.default_announcement_color))
        color = QColorDialog.getColor(current, self, "选择公告颜色")
        if not color.isValid():
            return

        self.announcements[index]['color'] = color.name()
        self.save_config()
        self.update_announcement_display()

    def delete_announcement(self, index: int):
        if index < 0 or index >= len(self.announcements):
            return

        reply = QMessageBox.question(
            self,
            "确认",
            "确定要删除该条公告吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self.announcements.pop(index)
            self.update_announcement_display()
            self.save_config()
        except Exception:
            pass

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
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                self.exposure = config.get('exposure', 0)
                self.time_position = config.get('time_position', 'top-right')
                self.timestamp_scale = float(config.get('timestamp_scale', 1.0))
                self.record_indicator_scale = float(config.get('record_indicator_scale', 1.0))
                self.camera_index = int(config.get('camera_index', 0))
                self.default_announcement_color = config.get('default_announcement_color', self.colors['text_primary'])

                raw_anns = config.get('announcements', [])
                self.announcements = []
                for ann in raw_anns if isinstance(raw_anns, list) else []:
                    if not isinstance(ann, dict):
                        continue
                    self.announcements.append({
                        'text': str(ann.get('text', '')).strip(),
                        'timestamp': str(ann.get('timestamp', '')).strip(),
                        'color': ann.get('color', self.default_announcement_color)
                    })
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        """Save configuration to file"""
        config = {
            'exposure': self.exposure,
            'time_position': self.time_position,
            'timestamp_scale': self.timestamp_scale,
            'record_indicator_scale': self.record_indicator_scale,
            'camera_index': self.camera_index,
            'default_announcement_color': self.default_announcement_color,
            'announcements': self.announcements
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
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
            self.cap = cv2.VideoCapture(self.camera_index)
            
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
            self.video_thread.timestamp_scale = self.timestamp_scale
            self.video_thread.record_indicator_scale = self.record_indicator_scale
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
