import cv2
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import datetime
import threading
import json
import os
from PIL import Image, ImageTk


class MonitoringApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitoring Software")
        self.root.geometry("1200x800")
        
        self.cap = None
        self.recording = False
        self.video_writer = None
        self.running = False
        
        self.exposure = 0
        self.time_position = "top-right"
        self.announcements = []
        
        self.config_file = "config.json"
        self.load_config()
        
        self.setup_ui()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        announcement_frame = ttk.LabelFrame(main_frame, text="Announcements", padding="5")
        announcement_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        announcement_frame.columnconfigure(0, weight=1)
        
        self.announcement_text = tk.Text(announcement_frame, height=4, wrap=tk.WORD, state=tk.DISABLED, bg="#fffacd")
        self.announcement_text.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        announcement_scrollbar = ttk.Scrollbar(announcement_frame, orient=tk.VERTICAL, command=self.announcement_text.yview)
        announcement_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.announcement_text.config(yscrollcommand=announcement_scrollbar.set)
        
        announcement_btn_frame = ttk.Frame(announcement_frame)
        announcement_btn_frame.grid(row=1, column=0, columnspan=2, pady=(5, 0))
        
        ttk.Button(announcement_btn_frame, text="Add Announcement", command=self.add_announcement).pack(side=tk.LEFT, padx=2)
        ttk.Button(announcement_btn_frame, text="Clear All", command=self.clear_announcements).pack(side=tk.LEFT, padx=2)
        
        self.update_announcement_display()
        
        video_frame = ttk.LabelFrame(main_frame, text="Video Feed", padding="5")
        video_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)
        
        self.video_label = ttk.Label(video_frame, text="Camera not started", background="black", foreground="white")
        self.video_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.start_btn = ttk.Button(control_frame, text="Start Camera", command=self.start_camera)
        self.start_btn.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop Camera", command=self.stop_camera, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        self.record_btn = ttk.Button(control_frame, text="Start Recording", command=self.toggle_recording, state=tk.DISABLED)
        self.record_btn.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        
        self.status_label = ttk.Label(control_frame, text="Status: Idle", foreground="blue")
        self.status_label.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N))
        
        ttk.Label(settings_frame, text="Exposure:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.exposure_scale = ttk.Scale(settings_frame, from_=-10, to=10, orient=tk.HORIZONTAL, 
                                       command=self.update_exposure, length=200)
        self.exposure_scale.set(self.exposure)
        self.exposure_scale.grid(row=0, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        self.exposure_value_label = ttk.Label(settings_frame, text=f"{self.exposure:.1f}")
        self.exposure_value_label.grid(row=0, column=2, pady=5)
        
        ttk.Label(settings_frame, text="Time Position:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.position_var = tk.StringVar(value=self.time_position)
        position_combo = ttk.Combobox(settings_frame, textvariable=self.position_var, 
                                     values=["top-left", "top-right", "bottom-left", "bottom-right"],
                                     state="readonly")
        position_combo.grid(row=1, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        position_combo.bind("<<ComboboxSelected>>", self.update_time_position)
        
        settings_frame.columnconfigure(1, weight=1)
        
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
        announcement = simpledialog.askstring("Add Announcement", 
                                             "Enter announcement message:",
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
        if messagebox.askyesno("Clear Announcements", "Are you sure you want to clear all announcements?"):
            self.announcements = []
            self.update_announcement_display()
            self.save_config()
            
    def update_announcement_display(self):
        self.announcement_text.config(state=tk.NORMAL)
        self.announcement_text.delete(1.0, tk.END)
        
        if not self.announcements:
            self.announcement_text.insert(tk.END, "No announcements")
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
                messagebox.showerror("Error", "Could not open camera")
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
            self.status_label.config(text="Status: Camera Running", foreground="green")
            
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
        self.status_label.config(text="Status: Idle", foreground="blue")
        self.video_label.config(image='', text="Camera stopped")
        
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
            self.record_btn.config(text="Stop Recording")
            self.status_label.config(text="Status: Recording", foreground="red")
        else:
            self.recording = False
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
            self.record_btn.config(text="Start Recording")
            self.status_label.config(text="Status: Camera Running", foreground="green")
            messagebox.showinfo("Recording Saved", "Video has been saved to recordings folder")
            
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
                    
                    rec_text = "REC"
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
