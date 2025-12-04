# 问题修复报告

## 问题描述

用户报告了两个主要问题：

1. **运行 `run.py` 时命令行窗口闪一下就退出**
2. **直接运行 `setup.py` 报错：error: no commands supplied**

## 问题分析

### 问题1：run.py 闪退
经过分析，发现以下原因：
1. `PyQt5.QtWinExtras` 模块在 Linux 上不存在，导致导入失败
2. `pyttsx3` 需要系统级依赖 eSpeak，在 Linux 上可能未安装
3. 在无图形界面的环境中运行 Qt 应用程序会导致崩溃

### 问题2：setup.py 使用错误
`setup.py` 是 Python 包安装脚本，需要指定命令参数，不能直接运行。

## 修复方案

### 1. 修复 run.py 闪退问题

#### 1.1 处理 Windows 特定模块
```python
# 修改前
from PyQt5.QtWinExtras import QtWin

# 修改后  
try:
    from PyQt5.QtWinExtras import QtWin
except ImportError:
    # QtWin is only available on Windows
    QtWin = None
```

#### 1.2 处理 TTS 引擎初始化
```python
# 修改前
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150)
tts_engine.setProperty('volume', 1.0)

# 修改后
try:
    tts_engine = pyttsx3.init()
    tts_engine.setProperty('rate', 150)
    tts_engine.setProperty('volume', 1.0)
    TTS_AVAILABLE = True
except (RuntimeError, ImportError):
    # TTS not available (e.g., eSpeak not installed on Linux)
    tts_engine = None
    TTS_AVAILABLE = False
```

#### 1.3 添加图形环境检查
在 `run.py` 中添加了 DISPLAY 环境变量检查：
```python
# Check for display environment early
if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
    print("错误：未检测到图形显示环境。")
    # ... 详细的错误信息和解决方案
    sys.exit(1)
```

#### 1.4 添加异常处理
在 `run.py` 和 `main()` 函数中添加了完整的异常处理，提供友好的错误信息。

### 2. 优化 setup.py

#### 2.1 改进依赖管理
```python
# 从 requirements.txt 自动读取依赖
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

install_requires=requirements,
```

#### 2.2 添加可选依赖
```python
extras_require={
    "tts": ["pyttsx3"],
    "dev": ["pytest", "black", "flake8"],
},
```

#### 2.3 完善元数据
添加了更完整的分类器、项目链接等信息。

## 新增文件

### 1. INSTALL.md
详细的安装和使用说明文档，包括：
- 依赖安装方法
- 多种运行方式
- 常见问题解决方案
- 系统要求

### 2. test_system.py
系统测试脚本，用于验证：
- 文件完整性
- 模块导入
- 依赖可用性
- 跨平台兼容性

## 测试结果

运行 `test_system.py` 的结果：
```
✓ 所有测试通过！程序可以正常运行。
```

## 使用方法

### 正确的运行方式

1. **直接运行（推荐）**：
   ```bash
   python run.py
   ```

2. **通过模块运行**：
   ```bash
   python -m monitoring_app
   ```

3. **安装后运行**：
   ```bash
   pip install .
   classmonitor
   ```

### setup.py 正确使用

```bash
# 安装包
pip install .

# 开发模式安装
pip install -e .

# 构建分发包
python setup.py sdist bdist_wheel

# 查看帮助
python setup.py --help
```

## 跨平台兼容性

修复后的代码现在支持：
- ✅ Windows（完整功能）
- ✅ Linux（核心功能，TTS 可选）
- ✅ macOS（核心功能）

## 总结

通过这些修复：
1. 解决了 run.py 在无图形环境下的闪退问题
2. 提供了清晰的错误信息和解决方案
3. 改善了跨平台兼容性
4. 优化了 setup.py 的使用体验
5. 添加了完整的测试和文档

用户现在可以：
- 在有图形界面的环境中正常运行程序
- 在无图形环境中获得清晰的错误提示
- 正确使用 setup.py 进行包管理
- 通过测试脚本验证系统状态