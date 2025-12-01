import cv2
import sys
import datetime
import threading
import json
import os
from PIL import Image, ImageQt
import math

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame, QScrollArea, QTextEdit
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QFont

from qfluentwidgets import (
    FluentIcon, PushButton, PrimaryPushButton, InfoBar, InfoBarPosition, 
    CardWidget, SubtitleLabel, CaptionLabel, BodyLabel, StrongBodyLabel,
    Slider, ComboBox, ScrollArea, SmoothScrollArea, TextEdit, LineEdit,
    MessageBox, Dialog, FluentStyleSheet, setTheme, Theme, isDarkTheme,
    InfoBadge, ProgressRing, StateToolTip, ToolTipFilter
)


class VideoThread(QThread):
    frame_ready = pyqtSignal(QImage)
    status_changed = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.recording = False
        self.cap = None
        self.video_writer = None
        self.exposure = 0
        self.time_position = "top-right"
        
    def run(self):
        self.running = True
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
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
                    cv2.putText(frame, rec_text, (10, 30), font, rec_font_scale, rec_color, rec_thickness)
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                self.frame_ready.emit(qt_image)
                
            self.msleep(50)
    
    def stop(self):
        self.running = False
        self.wait()


class MonitoringApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Fluent Design Colors
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
        self.buttons_visible = True
        
        self.exposure = 0
        self.time_position = "top-right"
        self.announcements = []
        
        self.config_file = "config.json"
        self.video_thread = None
        
        self.load_config()
        self.setup_ui()
        self.setup_timer()
        
    def setup_ui(self):
        self.setWindowTitle("智能监控系统")
        self.setGeometry(100, 100, 1200, 800)
        
        # Set application style - qfluentwidgets will automatically style components
        # Note: FluentStyleSheet.apply() requires specific parameters
        # The components will be styled automatically when created
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header with title and toggle button
        header_layout = QHBoxLayout()
        
        title_label = SubtitleLabel("智能监控系统")
        title_label.setAlignment(Qt.AlignLeft)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.toggle_btn = PushButton("隐藏控件")
        self.toggle_btn.clicked.connect(self.toggle_buttons_visibility)
        self.toggle_btn.setFixedWidth(120)
        header_layout.addWidget(self.toggle_btn)
        
        main_layout.addLayout(header_layout)
        
        # Video container with card design
        video_card = CardWidget()
        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(10, 10, 10, 10)
        
        # Video label
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
            }
        """)
        video_layout.addWidget(self.video_label)
        
        # Status bar
        self.status_label = BodyLabel("状态: 空闲")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {self.colors['primary']};
                font-family: 'Microsoft YaHei UI';
                font-weight: bold;
                padding: 5px 0px;
            }}
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        video_layout.addWidget(self.status_label)
        
        main_layout.addWidget(video_card)
        
        # Control panel (can be hidden)
        self.control_widget = QWidget()
        control_layout = QVBoxLayout(self.control_widget)
        
        control_card = CardWidget()
        control_inner_layout = QVBoxLayout(control_card)
        control_inner_layout.setContentsMargins(20, 15, 20, 15)
        
        control_title = SubtitleLabel("摄像头控制")
        control_title.setAlignment(Qt.AlignLeft)
        control_inner_layout.addWidget(control_title)
        
        # Camera buttons
        btn_layout = QHBoxLayout()
        
        self.start_btn = PrimaryPushButton("启动摄像头")
        self.start_btn.clicked.connect(self.start_camera)
        self.start_btn.setFixedWidth(120)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = PushButton("停止摄像头")
        self.stop_btn.clicked.connect(self.stop_camera)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedWidth(120)
        btn_layout.addWidget(self.stop_btn)
        
        self.record_btn = PushButton("开始录制")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setEnabled(False)
        self.record_btn.setFixedWidth(120)
        btn_layout.addWidget(self.record_btn)
        
        btn_layout.addStretch()
        control_inner_layout.addLayout(btn_layout)
        
        control_layout.addWidget(control_card)
        
        # Settings panel (can be hidden)
        self.settings_widget = QWidget()
        settings_layout = QVBoxLayout(self.settings_widget)
        
        settings_card = CardWidget()
        settings_inner_layout = QVBoxLayout(settings_card)
        settings_inner_layout.setContentsMargins(20, 15, 20, 15)
        
        settings_title = SubtitleLabel("设置")
        settings_title.setAlignment(Qt.AlignLeft)
        settings_inner_layout.addWidget(settings_title)
        
        # Exposure setting
        exposure_layout = QVBoxLayout()
        exposure_label = StrongBodyLabel("曝光调整:")
        exposure_layout.addWidget(exposure_label)
        
        exposure_control_layout = QHBoxLayout()
        
        self.exposure_scale = Slider(Qt.Horizontal)
        self.exposure_scale.setRange(-10, 10)
        self.exposure_scale.setValue(self.exposure)
        self.exposure_scale.valueChanged.connect(self.update_exposure)
        exposure_control_layout.addWidget(self.exposure_scale)
        
        self.exposure_value_label = QLabel(f"{self.exposure:.1f}")
        self.exposure_value_label.setFixedWidth(50)
        self.exposure_value_label.setAlignment(Qt.AlignCenter)
        exposure_control_layout.addWidget(self.exposure_value_label)
        
        exposure_layout.addLayout(exposure_control_layout)
        settings_inner_layout.addLayout(exposure_layout)
        
        # Time position setting
        position_layout = QVBoxLayout()
        position_label = StrongBodyLabel("时间位置:")
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
        
        settings_inner_layout.addLayout(position_layout)
        settings_layout.addWidget(settings_card)
        
        # Add control and settings to main layout
        main_layout.addWidget(self.control_widget)
        main_layout.addWidget(self.settings_widget)
        
        # Announcements section
        announcement_card = CardWidget()
        announcement_layout = QVBoxLayout(announcement_card)
        
        announcement_header_layout = QHBoxLayout()
        
        announcement_title = SubtitleLabel("通知公告")
        announcement_title.setAlignment(Qt.AlignLeft)
        announcement_header_layout.addWidget(announcement_title)
        
        announcement_header_layout.addStretch()
        
        add_announcement_btn = PrimaryPushButton("添加公告")
        add_announcement_btn.clicked.connect(self.add_announcement)
        add_announcement_btn.setFixedWidth(120)
        announcement_header_layout.addWidget(add_announcement_btn)
        
        clear_announcements_btn = PushButton("清空全部")
        clear_announcements_btn.clicked.connect(self.clear_announcements)
        clear_announcements_btn.setFixedWidth(120)
        announcement_header_layout.addWidget(clear_announcements_btn)
        
        announcement_layout.addLayout(announcement_header_layout)
        
        # Announcement text area
        self.announcement_text = QTextEdit()
        self.announcement_text.setReadOnly(True)
        self.announcement_text.setFixedHeight(100)
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
        
        main_layout.addWidget(announcement_card)
        
        # Set stretch factors
        main_layout.addStretch()
        
        self.update_announcement_display()
        
    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
    def load_config(self):
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
        config = {
            'exposure': self.exposure,
            'time_position': self.time_position,
            'announcements': self.announcements
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def add_announcement(self):
        dialog = Dialog("添加公告", "请输入公告内容:", self)
        dialog.yesButton.setText("确定")
        dialog.cancelButton.setText("取消")
        
        line_edit = LineEdit()
        dialog.contentLayout.addWidget(line_edit)
        
        if dialog.exec():
            announcement = line_edit.text()
            if announcement and announcement.strip():
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.announcements.append({
                    'text': announcement.strip(),
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
                
    def clear_announcements(self):
        dialog = MessageBox("清空公告", "确定要清空所有公告吗？", self)
        dialog.yesButton.setText("确定")
        dialog.cancelButton.setText("取消")
        
        if dialog.exec():
            self.announcements = []
            self.update_announcement_display()
            self.save_config()
            InfoBar.success(
                title="成功",
                content="公告已清空",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
    def update_announcement_display(self):
        self.announcement_text.clear()
        
        if not self.announcements:
            self.announcement_text.append("暂无公告")
        else:
            for i, ann in enumerate(self.announcements):
                text = f"[{ann['timestamp']}] {ann['text']}"
                if i > 0:
                    text = "\n" + text
                self.announcement_text.append(text)
                
    def update_exposure(self, value):
        self.exposure = value
        self.exposure_value_label.setText(f"{self.exposure:.1f}")
        if self.cap is not None:
            try:
                self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            except:
                pass
        self.save_config()
        
    def update_time_position(self, text):
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
        
    def toggle_buttons_visibility(self):
        self.buttons_visible = not self.buttons_visible
        if self.buttons_visible:
            self.control_widget.show()
            self.settings_widget.show()
            self.toggle_btn.setText("隐藏控件")
        else:
            self.control_widget.hide()
            self.settings_widget.hide()
            self.toggle_btn.setText("显示控件")
        
    def start_camera(self):
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
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {self.colors['success']};
                    font-family: 'Microsoft YaHei UI';
                    font-weight: bold;
                    padding: 5px 0px;
                }}
            """)
            self.video_label.setText("")
            
            # Start video thread
            self.video_thread = VideoThread()
            self.video_thread.cap = self.cap
            self.video_thread.exposure = self.exposure
            self.video_thread.time_position = self.time_position
            self.video_thread.frame_ready.connect(self.update_video_frame)
            self.video_thread.start()
            
    def stop_camera(self):
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
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {self.colors['primary']};
                font-family: 'Microsoft YaHei UI';
                font-weight: bold;
                padding: 5px 0px;
            }}
        """)
        self.video_label.setText("摄像头已停止")
        self.video_label.setPixmap(QPixmap())
        
    def toggle_recording(self):
        if not self.recording:
            if not os.path.exists('recordings'):
                os.makedirs('recordings')
                
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recordings/video_{timestamp}.avi"
            
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            fps = 20.0
            frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.video_writer = cv2.VideoWriter(filename, fourcc, fps, (frame_width, frame_height))
            
            self.recording = True
            if self.video_thread:
                self.video_thread.recording = True
                self.video_thread.video_writer = self.video_writer
            self.record_btn.setText("停止录制")
            self.status_label.setText("状态: 正在录制")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {self.colors['danger']};
                    font-family: 'Microsoft YaHei UI';
                    font-weight: bold;
                    padding: 5px 0px;
                }}
            """)
        else:
            self.recording = False
            if self.video_thread:
                self.video_thread.recording = False
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
            self.record_btn.setText("开始录制")
            self.status_label.setText("状态: 摄像头运行中")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {self.colors['success']};
                    font-family: 'Microsoft YaHei UI';
                    font-weight: bold;
                    padding: 5px 0px;
                }}
            """)
            InfoBar.success(
                title="录制完成",
                content="视频已保存到 recordings 文件夹",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
    @pyqtSlot(QImage)
    def update_video_frame(self, qt_image):
        # Scale image to fit the video label
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(
            self.video_label.size(), 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)
        
    def update_frame(self):
        # This method is kept for compatibility but actual frame updates 
        # are handled by the video thread
        pass
        
    def closeEvent(self, event):
        self.stop_camera()
        self.save_config()
        event.accept()


def main():
    # Create QApplication if it doesn't exist
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("智能监控系统")
    app.setOrganizationName("ClassMonitor")
    
    # Set theme
    setTheme(Theme.LIGHT)
    
    window = MonitoringApp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()