# ClassMonitor

A comprehensive monitoring software application with video recording, time overlay, exposure adjustment, and announcement management features.

## Features

1. **Video Recording with Time Overlay**
   - Record videos from your camera/webcam
   - Real-time timestamp display at adjustable corner positions
   - Choose from 4 positions: top-left, top-right, bottom-left, bottom-right
   - Videos saved in AVI format with timestamps in filename

2. **Exposure Adjustment**
   - Real-time exposure control with a slider
   - Range from -10 to +10
   - Instant feedback on video feed

3. **Announcement Table**
   - Display important announcements at the top of the interface
   - Add new announcements with timestamps
   - Clear all announcements when needed
   - Announcements persist between sessions
   - Highlighted display area for easy visibility

## Installation

1. Install Python 3.8 or higher

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Application

Run the monitoring application:
```bash
python monitoring_app.py
```

### Controls

#### Camera Operations
- **Start Camera**: Activates the webcam and displays live feed
- **Stop Camera**: Stops the camera feed and releases resources
- **Start Recording**: Begins recording video to file (camera must be running)
- **Stop Recording**: Stops recording and saves the video

#### Settings
- **Exposure Slider**: Adjust camera exposure from -10 to +10
- **Time Position**: Select where the timestamp appears on the video
  - Options: top-left, top-right, bottom-left, bottom-right

#### Announcements
- **Add Announcement**: Opens a dialog to add a new announcement message
- **Clear All**: Removes all announcements after confirmation

### Recorded Videos

All recorded videos are saved in the `recordings/` directory with the format:
```
video_YYYYMMDD_HHMMSS.avi
```

Example: `video_20241119_143022.avi`

### Configuration

Settings are automatically saved to `config.json` and include:
- Exposure level
- Time position preference
- All announcements

These settings persist between application sessions.

## Features Overview

### Video Feed Display
- Real-time video preview with timestamp overlay
- Recording indicator (red "REC" text) when recording is active
- Automatic video scaling to fit display area

### Announcement System
- Timestamped announcements for important messages
- Yellow highlighted display area for visibility
- Scrollable list for multiple announcements
- Persistent storage across sessions

### User Interface
- Clean, organized layout with labeled sections
- Intuitive controls and status indicators
- Color-coded status messages:
  - Blue: Idle
  - Green: Camera Running
  - Red: Recording

## Requirements

- Python 3.8+
- OpenCV (opencv-python)
- NumPy
- Pillow
- Tkinter (usually included with Python)
- Webcam or camera device

## Troubleshooting

### Camera Not Opening
- Ensure your camera is not being used by another application
- Check camera permissions in your operating system
- Try changing the camera index in the code (line: `cv2.VideoCapture(0)`)

### Recording Issues
- Ensure you have write permissions in the project directory
- Check available disk space
- The `recordings/` folder will be created automatically if it doesn't exist

### Exposure Control Not Working
- Some cameras may not support exposure adjustment via OpenCV
- The feature depends on your camera's capabilities and drivers

## License

See LICENSE file for details.
