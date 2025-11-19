# Quick Start Guide

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Simply run:
```bash
python monitoring_app.py
```

## First Steps

1. **Start the Camera**
   - Click the "Start Camera" button
   - You should see your webcam feed appear

2. **Add an Announcement**
   - Click "Add Announcement" in the announcement section
   - Type your message and click OK
   - The announcement will appear with a timestamp

3. **Adjust Settings**
   - Use the **Exposure** slider to adjust brightness
   - Select **Time Position** to change where the timestamp appears on the video

4. **Record a Video**
   - With the camera running, click "Start Recording"
   - The recording indicator (red "REC") will appear
   - Click "Stop Recording" when done
   - Find your video in the `recordings/` folder

## Tips

- All settings are automatically saved and will be restored when you restart the app
- Announcements persist between sessions
- Videos are saved with timestamps in the filename for easy organization
- The timestamp on the video can be positioned at any corner

## System Requirements

- Python 3.8 or higher
- Working webcam/camera
- At least 100MB free disk space for recordings

## Support

For issues or questions, please check the README.md file for detailed documentation and troubleshooting tips.
