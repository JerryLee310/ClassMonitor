import cv2
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import datetime
import threading
import json
import os
from PIL import Image, ImageTk
import math


class MonitoringApp:
    def __init__(self, root):
        self.root = root
        self.root.title("智能监控系统")
        self.root.geometry("1200x800")
        self.root.configure(bg='#F3F2F1')
        
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
        self.load_config()
        
        self.setup_styles()
        self.setup_ui()
        
    def setup_styles(self):
        """Setup Fluent Design styles for ttk widgets"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles with Fluent Design colors and rounded corners
        style.configure('Fluent.TFrame', background=self.colors['background'], relief='flat')
        try:
            style.layout('Fluent.TFrame', style.layout('TFrame'))
        except:
            pass
            
        style.configure('FluentCard.TFrame', background=self.colors['surface'], relief='flat', borderwidth=1)
        try:
            style.layout('FluentCard.TFrame', style.layout('TFrame'))
        except:
            pass
            
        style.configure('Fluent.TLabel', background=self.colors['background'], foreground=self.colors['text_primary'], font=('Microsoft YaHei UI', 10))
        try:
            style.layout('Fluent.TLabel', style.layout('TLabel'))
        except:
            pass
            
        style.configure('FluentTitle.TLabel', background=self.colors['background'], foreground=self.colors['text_primary'], font=('Microsoft YaHei UI', 12, 'bold'))
        try:
            style.layout('FluentTitle.TLabel', style.layout('TLabel'))
        except:
            pass
        style.configure('Fluent.TButton', 
                       background=self.colors['primary'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Microsoft YaHei UI', 10),
                       padding=(20, 8),
                       relief='flat')
        try:
            style.layout('Fluent.TButton', style.layout('TButton'))
        except:
            pass
            
        style.map('Fluent.TButton',
                 background=[('active', self.colors['accent']),
                           ('!disabled', self.colors['primary']),
                           ('disabled', '#CCCCCC')])
        
        style.configure('FluentSuccess.TButton',
                       background=self.colors['success'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Microsoft YaHei UI', 10),
                       padding=(20, 8),
                       relief='flat')
        try:
            style.layout('FluentSuccess.TButton', style.layout('TButton'))
        except:
            pass
            
        style.map('FluentSuccess.TButton',
                 background=[('active', '#0E6F0E'),
                           ('!disabled', self.colors['success']),
                           ('disabled', '#CCCCCC')])
        
        style.configure('FluentDanger.TButton',
                       background=self.colors['danger'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Microsoft YaHei UI', 10),
                       padding=(20, 8),
                       relief='flat')
        try:
            style.layout('FluentDanger.TButton', style.layout('TButton'))
        except:
            pass
            
        style.map('FluentDanger.TButton',
                 background=[('active', '#C02E2E'),
                           ('!disabled', self.colors['danger']),
                           ('disabled', '#CCCCCC')])
        
        style.configure('Fluent.TScale', 
                         background=self.colors['surface'],
                         troughcolor=self.colors['border'],
                         borderwidth=0,
                         lightcolor=self.colors['primary'],
                         darkcolor=self.colors['primary'],
                         relief='flat')
        
        # Create custom layout for Scale and its variants, fallback to default
        try:
            style.layout('Fluent.TScale', style.layout('TScale'))
        except:
            pass
        
        try:
            style.layout('Horizontal.Fluent.TScale', style.layout('Horizontal.TScale'))
        except:
            pass
        
        try:
            style.layout('Vertical.Fluent.TScale', style.layout('Vertical.TScale'))
        except:
            pass
        
        style.configure('Fluent.TCombobox',
                         fieldbackground=self.colors['surface'],
                         background=self.colors['surface'],
                         borderwidth=1,
                         relief='solid',
                         font=('Microsoft YaHei UI', 10))
        style.map('Fluent.TCombobox',
                  focuscolor=[('focus', self.colors['primary'])])
        
        # Create custom layout for Combobox and its variants, fallback to default
        try:
            style.layout('Fluent.TCombobox', style.layout('TCombobox'))
        except:
            pass
        
        # Add hover effect for buttons
        self.setup_button_hover_effects()
        
    def setup_button_hover_effects(self):
        """Setup hover effects for buttons"""
        self.button_hover_enabled = True
        
    def on_button_enter(self, event):
        """Handle button enter event"""
        if self.button_hover_enabled and event.widget['state'] != 'disabled':
            event.widget.configure(cursor='hand2')
            
    def on_button_leave(self, event):
        """Handle button leave event"""
        event.widget.configure(cursor='arrow')
        
    def toggle_buttons_visibility(self):
        """Toggle visibility of control buttons"""
        self.buttons_visible = not self.buttons_visible
        if self.buttons_visible:
            self.control_frame.grid()
            self.settings_frame.grid()
            self.toggle_btn.config(text="隐藏控件")
        else:
            self.control_frame.grid_remove()
            self.settings_frame.grid_remove()
            self.toggle_btn.config(text="显示控件")
        
    def setup_ui(self):
        # Main container with Fluent Design
        main_frame = ttk.Frame(self.root, style='Fluent.TFrame', padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Header with title and toggle button
        header_frame = ttk.Frame(main_frame, style='Fluent.TFrame')
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        title_label = ttk.Label(header_frame, text="智能监控系统", style='FluentTitle.TLabel')
        title_label.pack(side=tk.LEFT)
        
        self.toggle_btn = ttk.Button(header_frame, text="隐藏控件", 
                                    command=self.toggle_buttons_visibility,
                                    style='Fluent.TButton')
        self.toggle_btn.pack(side=tk.RIGHT)
        self.toggle_btn.bind('<Enter>', self.on_button_enter)
        self.toggle_btn.bind('<Leave>', self.on_button_leave)
        
        # Video container with card design
        video_container = ttk.Frame(main_frame, style='FluentCard.TFrame')
        video_container.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
        video_container.columnconfigure(0, weight=1)
        video_container.rowconfigure(0, weight=1)
        
        # Video label with modern styling
        self.video_label = tk.Label(video_container, 
                                   text="摄像头未启动", 
                                   bg="#000000", 
                                   fg="#FFFFFF",
                                   font=('Microsoft YaHei UI', 14),
                                   relief='flat')
        self.video_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Status bar at bottom of video
        self.status_label = tk.Label(video_container, 
                                   text="状态: 空闲", 
                                   bg=self.colors['surface'],
                                   fg=self.colors['primary'],
                                   font=('Microsoft YaHei UI', 10, 'bold'),
                                   pady=5)
        self.status_label.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=(0, 10))
        
        # Control panel (can be hidden)
        self.control_frame = ttk.Frame(main_frame, style='FluentCard.TFrame')
        self.control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # Camera controls
        camera_frame = ttk.Frame(self.control_frame, style='Fluent.TFrame')
        camera_frame.pack(fill=tk.X, padx=20, pady=15)
        
        ttk.Label(camera_frame, text="摄像头控制", style='FluentTitle.TLabel').pack(anchor=tk.W, pady=(0, 10))
        
        btn_frame = ttk.Frame(camera_frame, style='Fluent.TFrame')
        btn_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(btn_frame, text="启动摄像头", 
                                   command=self.start_camera,
                                   style='FluentSuccess.TButton')
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.start_btn.bind('<Enter>', self.on_button_enter)
        self.start_btn.bind('<Leave>', self.on_button_leave)
        
        self.stop_btn = ttk.Button(btn_frame, text="停止摄像头", 
                                  command=self.stop_camera, 
                                  state=tk.DISABLED,
                                  style='FluentDanger.TButton')
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_btn.bind('<Enter>', self.on_button_enter)
        self.stop_btn.bind('<Leave>', self.on_button_leave)
        
        self.record_btn = ttk.Button(btn_frame, text="开始录制", 
                                    command=self.toggle_recording, 
                                    state=tk.DISABLED,
                                    style='Fluent.TButton')
        self.record_btn.pack(side=tk.LEFT)
        self.record_btn.bind('<Enter>', self.on_button_enter)
        self.record_btn.bind('<Leave>', self.on_button_leave)
        
        # Settings panel (can be hidden)
        self.settings_frame = ttk.Frame(main_frame, style='FluentCard.TFrame')
        self.settings_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        
        settings_container = ttk.Frame(self.settings_frame, style='Fluent.TFrame')
        settings_container.pack(fill=tk.X, padx=20, pady=15)
        
        ttk.Label(settings_container, text="设置", style='FluentTitle.TLabel').pack(anchor=tk.W, pady=(0, 15))
        
        # Exposure setting
        exposure_frame = ttk.Frame(settings_container, style='Fluent.TFrame')
        exposure_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(exposure_frame, text="曝光调整:", style='Fluent.TLabel').pack(anchor=tk.W, pady=(0, 5))
        
        exposure_control = ttk.Frame(exposure_frame, style='Fluent.TFrame')
        exposure_control.pack(fill=tk.X)
        
        self.exposure_scale = ttk.Scale(exposure_control, from_=-10, to=10, 
                                       orient=tk.HORIZONTAL,
                                       command=self.update_exposure,
                                       style='Fluent.TScale',
                                       length=300)
        self.exposure_scale.set(self.exposure)
        self.exposure_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.exposure_value_label = ttk.Label(exposure_control, text=f"{self.exposure:.1f}", 
                                            style='Fluent.TLabel',
                                            width=5)
        self.exposure_value_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Time position setting
        position_frame = ttk.Frame(settings_container, style='Fluent.TFrame')
        position_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(position_frame, text="时间位置:", style='Fluent.TLabel').pack(anchor=tk.W, pady=(0, 5))
        
        self.position_var = tk.StringVar(value=self.time_position)
        position_values = {
            "top-left": "左上角",
            "top-right": "右上角", 
            "bottom-left": "左下角",
            "bottom-right": "右下角"
        }
        
        position_combo = ttk.Combobox(position_frame, 
                                    textvariable=self.position_var,
                                    values=list(position_values.keys()),
                                    state="readonly",
                                    style='Fluent.TCombobox',
                                    width=20)
        position_combo.pack(anchor=tk.W)
        position_combo.bind("<<ComboboxSelected>>", self.update_time_position)
        
        # Announcements section
        announcement_frame = ttk.Frame(main_frame, style='FluentCard.TFrame')
        announcement_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(20, 0))
        announcement_frame.columnconfigure(0, weight=1)
        announcement_frame.rowconfigure(1, weight=1)
        
        announcement_header = ttk.Frame(announcement_frame, style='Fluent.TFrame')
        announcement_header.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=20, pady=(15, 10))
        announcement_header.columnconfigure(0, weight=1)
        
        ttk.Label(announcement_header, text="通知公告", style='FluentTitle.TLabel').pack(side=tk.LEFT)
        
        announcement_btn_frame = ttk.Frame(announcement_header, style='Fluent.TFrame')
        announcement_btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(announcement_btn_frame, text="添加公告", 
                  command=self.add_announcement,
                  style='Fluent.TButton').pack(side=tk.LEFT, padx=(0, 10))
        announcement_btn_frame.winfo_children()[0].bind('<Enter>', self.on_button_enter)
        announcement_btn_frame.winfo_children()[0].bind('<Leave>', self.on_button_leave)
        
        ttk.Button(announcement_btn_frame, text="清空全部", 
                  command=self.clear_announcements,
                  style='FluentDanger.TButton').pack(side=tk.LEFT)
        announcement_btn_frame.winfo_children()[1].bind('<Enter>', self.on_button_enter)
        announcement_btn_frame.winfo_children()[1].bind('<Leave>', self.on_button_leave)
        
        # Announcement text area
        text_frame = ttk.Frame(announcement_frame, style='Fluent.TFrame')
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=20, pady=(0, 15))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.announcement_text = tk.Text(text_frame, height=4, wrap=tk.WORD, 
                                        state=tk.DISABLED, 
                                        bg="#FAFAFA",
                                        fg=self.colors['text_primary'],
                                        font=('Microsoft YaHei UI', 10),
                                        relief='flat',
                                        borderwidth=1,
                                        insertbackground=self.colors['primary'])
        self.announcement_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        announcement_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, 
                                            command=self.announcement_text.yview)
        announcement_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.announcement_text.config(yscrollcommand=announcement_scrollbar.set)
        
        self.update_announcement_display()
        
        # Configure grid weights
        main_frame.rowconfigure(4, weight=1)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
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
        announcement = simpledialog.askstring("添加公告", 
                                             "请输入公告内容:",
                                             parent=self.root)
        if announcement and announcement.strip():
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.announcements.append({
                'text': announcement.strip(),
                'timestamp': timestamp
            })
            self.update_announcement_display()
            self.save_config()
            
    def clear_announcements(self):
        if messagebox.askyesno("清空公告", "确定要清空所有公告吗？"):
            self.announcements = []
            self.update_announcement_display()
            self.save_config()
            
    def update_announcement_display(self):
        self.announcement_text.config(state=tk.NORMAL)
        self.announcement_text.delete(1.0, tk.END)
        
        if not self.announcements:
            self.announcement_text.insert(tk.END, "暂无公告")
        else:
            for i, ann in enumerate(self.announcements):
                text = f"[{ann['timestamp']}] {ann['text']}"
                if i > 0:
                    text = "\n" + text
                self.announcement_text.insert(tk.END, text)
                
        self.announcement_text.config(state=tk.DISABLED)
        
    def update_exposure(self, value):
        self.exposure = float(value)
        self.exposure_value_label.config(text=f"{self.exposure:.1f}")
        if self.cap is not None:
            try:
                self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            except:
                pass
        self.save_config()
        
    def update_time_position(self, event=None):
        self.time_position = self.position_var.get()
        self.save_config()
        
    def start_camera(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            
            if not self.cap.isOpened():
                messagebox.showerror("错误", "无法打开摄像头")
                self.cap = None
                return
                
            try:
                self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            except:
                pass
                
            self.running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.record_btn.config(state=tk.NORMAL)
            self.status_label.config(text="状态: 摄像头运行中", fg=self.colors['success'])
            self.video_label.config(text='')
            
            self.update_frame()
            
    def stop_camera(self):
        if self.recording:
            self.toggle_recording()
            
        self.running = False
        
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.record_btn.config(state=tk.DISABLED)
        self.status_label.config(text="状态: 空闲", fg=self.colors['primary'])
        self.video_label.config(image='', text="摄像头已停止")
        
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
            self.record_btn.config(text="停止录制")
            self.status_label.config(text="状态: 正在录制", fg=self.colors['danger'])
        else:
            self.recording = False
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
            self.record_btn.config(text="开始录制")
            self.status_label.config(text="状态: 摄像头运行中", fg=self.colors['success'])
            messagebox.showinfo("录制完成", "视频已保存到 recordings 文件夹")
            
    def update_frame(self):
        if self.running and self.cap is not None:
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
                img = Image.fromarray(frame_rgb)
                
                display_width = self.video_label.winfo_width()
                display_height = self.video_label.winfo_height()
                
                if display_width > 1 and display_height > 1:
                    img_width, img_height = img.size
                    ratio = min(display_width / img_width, display_height / img_height)
                    new_width = int(img_width * ratio)
                    new_height = int(img_height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.config(image=imgtk, text='')
                
            self.root.after(50, self.update_frame)
            
    def on_closing(self):
        self.stop_camera()
        self.save_config()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MonitoringApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
