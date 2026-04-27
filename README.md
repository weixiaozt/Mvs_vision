# MVS Vision - 工业视觉检测系统

跨平台桌面应用，基于 PySide6 开发。

## 环境要求

- Python 3.11+
- PySide6 6.4+
- numpy, opencv-python

## 首次安装

### macOS / Linux

```bash
cd mvs_vision
./setup_env.sh
```

### Windows

```cmd
cd mvs_vision
setup_env.bat
```

## 启动运行

### macOS / Linux

```bash
cd mvs_vision
source venv/bin/activate
python main.py
```

或者使用快捷脚本：

```bash
./start.sh
```

### Windows

```cmd
cd mvs_vision
venv\Scripts\activate.bat
python main.py
```

或者使用快捷脚本：

```cmd
start.bat
```

## 项目结构

```
mvs_vision/
├── main.py                 # 入口文件
├── requirements.txt        # 依赖列表
├── setup_env.sh / .bat     # 环境初始化脚本
├── start.sh / .bat         # 快捷启动脚本
├── src/
│   ├── ui/
│   │   ├── main_window.py  # 主窗口
│   │   ├── sidebar.py      # 侧边栏导航
│   │   ├── camera_view.py  # 相机预览
│   │   ├── control_panel.py# 参数控制面板
│   │   └── styles.py       # 全局QSS样式
│   └── core/
│       └── vision_engine.py# 视觉引擎核心
```
