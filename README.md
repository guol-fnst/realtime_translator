# 实时日语转中文字幕翻译系统

实时捕获 Windows 系统音频（如 Teams 会议），通过 GPU 加速进行日语语音识别和中文翻译，显示为悬浮字幕。

## 功能特点

- 🎙️ **系统音频捕获**: 使用 WASAPI Loopback 捕获任何应用程序的音频
- 🗣️ **日语语音识别**: 通过服务端 faster-whisper 进行高精度识别
- 📝 **实时翻译**: 使用 Ollama LLM (qwen2.5:14b) 日语转中文
- 🖥️ **悬浮字幕**: 透明置顶窗口，可拖拽移动
- 📡 **字幕共享**: WebSocket 服务器支持多用户同时查看
- 📊 **GPU 监控**: 显示服务器 GPU 利用率

## 系统要求

- Windows 10/11
- Python 3.8+
- 服务端需要:
  - Ubuntu 服务器
  - NVIDIA GPU (RTX 3060 20GB)
  - Ollama + OpenWebUI
  - faster-whisper API 服务

## 快速开始

### 1. 安装

```bash
# 运行安装脚本
install.bat
```

或手动安装:

```bash
pip install -r requirements.txt
```

### 2. 运行

```bash
# 运行主程序
run.bat

# 或
python src/main.py
```

### 3. 测试

```bash
# 测试服务器连接
python src/main.py --test-api

# 测试音频捕获
python src/main.py --test-audio
```

## 字幕共享

主程序启动后会自动开启 WebSocket 服务器 (默认端口 8765)。

其他用户可以通过客户端连接:

```bash
python src/client.py --server ws://你的IP:8765
```

## 打包为独立程序

```bash
build.bat
```

生成的可执行文件: `dist/JapaneseTranslator.exe`

## 配置

配置文件保存在: `%APPDATA%/JapaneseTranslator/config.json`

主要配置项:
- `server_url`: OpenWebUI 服务器地址
- `translation_model`: 翻译模型 (默认 qwen2.5:14b)
- `sharing_port`: 共享端口 (默认 8765)
- `subtitle_font_size`: 字幕字体大小

## 服务端部署

需要在 Ubuntu 服务器上部署 faster-whisper API 服务。

请参考: [faster-whisper-server](https://github.com/fedirz/faster-whisper-server)

```bash
# Docker 部署示例
docker run -d --gpus all \
  -p 8000:8000 \
  fedirz/faster-whisper-server
```

## 项目结构

```
translater/
├── src/
│   ├── main.py           # 主程序
│   ├── config.py         # 配置管理
│   ├── audio_capture.py  # 音频捕获
│   ├── speech_recognition.py  # 语音识别
│   ├── translator.py     # 翻译
│   ├── subtitle_overlay.py    # 字幕窗口
│   ├── sharing_server.py      # 共享服务
│   ├── gpu_monitor.py    # GPU 监控
│   └── client.py         # 客户端
├── requirements.txt
├── install.bat
├── build.bat
└── run.bat
```

## 许可证

MIT License
