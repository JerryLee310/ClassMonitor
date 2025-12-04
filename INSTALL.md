# 安装和使用说明

## 安装依赖

在运行程序之前，请先安装所有依赖包：

```bash
pip install -r requirements.txt
```

## 运行程序

### 方法1：直接运行（推荐）
```bash
python run.py
```

### 方法2：通过模块运行
```bash
python -m monitoring_app
```

### 方法3：安装后运行
```bash
# 安装到系统
pip install .

# 然后可以直接运行
classmonitor
```

## setup.py 使用方法

`setup.py` 是 Python 包安装脚本，不能直接运行。需要指定命令：

### 安装包
```bash
pip install .
```

### 开发模式安装
```bash
pip install -e .
```

### 构建分发包
```bash
python setup.py sdist bdist_wheel
```

### 查看帮助
```bash
python setup.py --help
```

## 系统要求

### Windows
- Python 3.8+
- 无需额外依赖

### Linux
- Python 3.8+
- 图形界面环境（X11 或 Wayland）
- 可选：espeak 或 espeak-ng（用于语音功能）

### macOS
- Python 3.8+
- 支持的 macOS 版本

## 常见问题

### 1. "未检测到图形显示环境"
这通常发生在：
- SSH 连接未启用 X11 转发
- 无图形界面的服务器环境
- WSL 未安装 X 服务器

**解决方案：**
- SSH: `ssh -X username@hostname`
- WSL: 安装 VcXsrv 或 Xming
- 服务器: 使用支持图形界面的环境

### 2. "TTS error: eSpeak not installed"
语音功能需要 espeak，可选安装：
```bash
# Ubuntu/Debian
sudo apt-get install espeak

# CentOS/RHEL
sudo yum install espeak

# macOS
brew install espeak
```

### 3. "ModuleNotFoundError: No module named 'PyQt5.QtWinExtras'"
这个错误已经在代码中修复，程序会自动处理 Windows 特定模块的缺失。

## 开发说明

如果您想修改或扩展程序：

1. 克隆仓库
2. 安装开发依赖：`pip install -r requirements.txt`
3. 运行：`python run.py`
4. 修改代码后可以直接运行测试

## 项目结构

```
.
├── run.py              # 主启动脚本
├── monitoring_app.py   # 主应用程序
├── setup.py           # 安装脚本
├── requirements.txt   # 依赖列表
├── windows_admin.py   # Windows 特定功能
└── config.json        # 配置文件（自动生成）
```