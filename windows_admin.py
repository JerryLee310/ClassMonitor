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
        script_path = os.path.abspath(sys.argv[0])
        params = subprocess.list2cmdline([script_path] + sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        if ret > 32:  # Success
            sys.exit()
        else:
            # User denied or error occurred
            print(f"UAC request denied or failed (code: {ret})")
            return False
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


def deny_explorer_access(directory_path):
    """
    Set directory permissions to allow access only for current user and SYSTEM.
    Note: DENY ACEs take precedence over ALLOW ACEs, so we only use ALLOW ACEs.
    Requires administrator privileges.
    """
    if sys.platform != 'win32':
        return False

    if not WINDOWS_MODULES_AVAILABLE:
        return False

    try:
        import win32security
        import ntsecuritycon as con

        # Get the current process SID
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32security.TOKEN_QUERY
        )
        user_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]

        # Create a security descriptor
        sd = win32security.SECURITY_DESCRIPTOR()

        # Create a DACL (Discretionary Access Control List)
        dacl = win32security.ACL()

        # Allow full control for current user/process
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION,
            con.FILE_ALL_ACCESS,
            user_sid
        )

        # Allow full control for SYSTEM
        system_sid = win32security.ConvertStringSidToSid('S-1-5-18')
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION,
            con.FILE_ALL_ACCESS,
            system_sid
        )

        # Allow full control for Administrators group
        admin_sid = win32security.ConvertStringSidToSid('S-1-5-32-544')
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION,
            con.FILE_ALL_ACCESS,
            admin_sid
        )

        # Set the DACL to the security descriptor (DACL present, no default DACL)
        sd.SetSecurityDescriptorDacl(1, dacl, 0)

        # Apply the security descriptor to the directory
        win32security.SetFileSecurity(
            directory_path,
            win32security.DACL_SECURITY_INFORMATION,
            sd
        )

        return True
    except Exception as e:
        print(f"Failed to set directory permissions: {e}")
        return False


def protect_directories(directories):
    """
    Protect multiple directories from Explorer access.
    When not running as admin, ensures directories are accessible.
    """
    if sys.platform != 'win32':
        return False

    if not is_admin():
        print("Not running as administrator, ensuring directory accessibility")
        # Create directories but don't apply restrictive permissions
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"Failed to create directory {directory}: {e}")
        return False

    results = []
    for directory in directories:
        # Ensure directory exists
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"Failed to create directory {directory}: {e}")
                results.append(False)
                continue

        # Hide the directory
        try:
            import win32api
            import win32con
            win32api.SetFileAttributes(directory, win32con.FILE_ATTRIBUTE_HIDDEN | win32con.FILE_ATTRIBUTE_SYSTEM)
        except Exception as e:
            print(f"Failed to hide directory {directory}: {e}")

        # Apply access restrictions (allow only current user, SYSTEM, Administrators)
        result = deny_explorer_access(directory)
        results.append(result)

    return all(results)


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
