#!/usr/bin/env python3
"""
Application entry point with Windows protection features.
"""

import sys
import os
import os.path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check for display environment early
if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
    print("错误：未检测到图形显示环境。")
    print("这可能是因为：")
    print("1. 在 SSH 会话中运行但未启用 X11 转发")
    print("2. 在无图形界面的服务器环境中运行")
    print("3. 未设置 DISPLAY 环境变量")
    print("\n解决方案：")
    print("- 如果使用 SSH，请使用: ssh -X username@hostname")
    print("- 如果在本地 Linux 上，请确保已启动图形界面")
    print("- 如果在 Windows WSL 中，请安装 X 服务器（如 VcXsrv）")
    sys.exit(1)

# Try to protect the process on Windows
try:
    from windows_admin import is_admin, request_admin
    if sys.platform == 'win32':
        if not is_admin():
            request_admin()
except ImportError:
    pass

# Import and run the main application
try:
    from monitoring_app import main
    
    if __name__ == "__main__":
        main()
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖包：")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    if "platform plugin" in str(e) or "Could not load the Qt platform plugin" in str(e):
        print("图形界面初始化失败。这可能是因为：")
        print("1. 在无图形界面的环境中运行")
        print("2. 缺少必要的图形库")
        print("请在支持图形界面的环境中运行此程序。")
    else:
        print(f"程序启动失败: {e}")
    sys.exit(1)
