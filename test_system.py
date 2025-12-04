#!/usr/bin/env python3
"""
测试脚本 - 验证程序的基本功能
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有模块导入"""
    print("测试模块导入...")
    
    try:
        import monitoring_app
        print("✓ monitoring_app 导入成功")
    except ImportError as e:
        print(f"✗ monitoring_app 导入失败: {e}")
        return False
    
    try:
        import windows_admin
        print("✓ windows_admin 导入成功")
    except ImportError as e:
        if "windll" in str(e):
            print("✓ windows_admin 导入跳过（仅限 Windows）")
        else:
            print(f"✗ windows_admin 导入失败: {e}")
            return False
    
    return True

def test_dependencies():
    """测试关键依赖"""
    print("\n测试关键依赖...")
    
    dependencies = [
        ('cv2', 'OpenCV'),
        ('numpy', 'NumPy'),
        ('PIL', 'Pillow'),
        ('PyQt5', 'PyQt5'),
        ('qfluentwidgets', 'QFluentWidgets'),
        ('cryptography', 'Cryptography'),
    ]
    
    all_ok = True
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"✓ {name} 可用")
        except ImportError:
            print(f"✗ {name} 不可用")
            all_ok = False
    
    return all_ok

def test_optional_dependencies():
    """测试可选依赖"""
    print("\n测试可选依赖...")
    
    try:
        import pyttsx3
        print("✓ pyttsx3 (TTS) 可用")
        return True
    except ImportError:
        print("✗ pyttsx3 (TTS) 不可用（可选，不影响主要功能）")
        return False

def test_files():
    """测试必要文件"""
    print("\n测试必要文件...")
    
    required_files = [
        'monitoring_app.py',
        'windows_admin.py', 
        'run.py',
        'setup.py',
        'requirements.txt',
        'README.md',
    ]
    
    all_ok = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file} 存在")
        else:
            print(f"✗ {file} 不存在")
            all_ok = False
    
    return all_ok

def main():
    """主测试函数"""
    print("ClassMonitor 系统测试")
    print("=" * 40)
    
    tests = [
        ("文件检查", test_files),
        ("模块导入", test_imports), 
        ("关键依赖", test_dependencies),
        ("可选依赖", test_optional_dependencies),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} 测试失败: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 40)
    print("测试结果汇总:")
    
    all_passed = True
    for name, result in results:
        status = "通过" if result else "失败"
        print(f"  {name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✓ 所有测试通过！程序可以正常运行。")
        print("\n运行程序:")
        print("  python run.py")
    else:
        print("✗ 部分测试失败，请检查上述问题。")
        print("\n安装依赖:")
        print("  pip install -r requirements.txt")

if __name__ == "__main__":
    main()