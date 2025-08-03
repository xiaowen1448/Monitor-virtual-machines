# VirtualBox虚拟机监控系统

一个基于Web的VirtualBox虚拟机监控和管理系统，可以自动扫描虚拟机、监控状态、自动启动已停止的虚拟机。

## 功能特性

- 🔍 **自动扫描**: 自动发现VirtualBox虚拟机目录中的所有虚拟机
- 📊 **状态监控**: 实时显示虚拟机运行状态（运行中、已关闭、已暂停等）
- ⚡ **自动启动**: 自动启动已停止的虚拟机
- 🌐 **Web界面**: 现代化的Web管理界面
- 🔄 **实时刷新**: 支持自动刷新虚拟机状态
- 📱 **响应式设计**: 支持桌面和移动设备访问
- 📝 **详细日志**: 完整的操作日志记录

## 系统要求

- Python 3.7+
- VirtualBox 6.0+
- Flask (Python包)

## 安装步骤

### 1. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 2. 确保VirtualBox已安装

系统会自动检测VirtualBox安装路径，支持以下平台：
- Windows
- macOS
- Linux

### 3. 启动监控系统

#### 方法1: 使用批处理文件（推荐）
```bash
# Windows
run_simple.bat

# 或者
run.bat
```

#### 方法2: 直接运行Python脚本
```bash
python vbox_web.py
```

#### 方法3: 使用启动脚本
```bash
python start_monitor.py
```

## 使用方法

### 启动系统

1. 运行启动脚本：
   ```bash
   python start_monitor.py
   ```

2. 打开浏览器访问：
   ```
   http://localhost:5000
   ```

### Web界面功能

#### 控制面板
- **刷新**: 手动刷新虚拟机列表
- **扫描**: 重新扫描虚拟机目录
- **自动刷新**: 每30秒自动刷新状态
- **自动监控**: 启用自动监控功能

#### 快速操作
- **启动所有已停止的虚拟机**: 自动启动所有关闭的虚拟机
- **启动所有虚拟机**: 启动所有虚拟机
- **停止所有虚拟机**: 停止所有虚拟机

#### 虚拟机管理
- 查看虚拟机状态
- 启动/停止单个虚拟机
- 查看虚拟机详细信息
- 实时状态更新

## API接口

### 获取虚拟机列表
```
GET /api/vms
```

### 启动虚拟机
```
GET /api/vm/{vm_name}/start
```

### 停止虚拟机
```
GET /api/vm/{vm_name}/stop
```

### 获取虚拟机详情
```
GET /api/vm/{vm_name}/info
```

### 开始监控
```
GET /api/monitor/start?interval=60
```

### 停止监控
```
GET /api/monitor/stop
```

### 获取监控状态
```
GET /api/monitor/status
```

### 手动执行自动启动
```
GET /api/auto_start
```

### 重新扫描虚拟机
```
GET /api/scan
```

## 配置文件

系统会自动创建 `config.py` 配置文件，可以修改以下设置：

### 基本配置
```python
# VirtualBox虚拟机目录路径
VBOX_DIR = ""

# VirtualBox可执行文件路径
VBOXMANAGE_PATH = ""

# 监控间隔（秒）
MONITOR_INTERVAL = 60

# Web服务端口
WEB_PORT = 5000

# Web服务主机
WEB_HOST = "0.0.0.0"

# 日志级别
LOG_LEVEL = "INFO"

# 自动启动已停止的虚拟机
AUTO_START_STOPPED_VMS = True
```

### 高级配置
```python
# VirtualBox启动类型 (headless, gui, sdl)
VBOX_START_TYPE = "headless"

# 是否启用自动检测VirtualBox路径
AUTO_DETECT_VBOXMANAGE = True

# 是否启用详细日志
VERBOSE_LOGGING = True

# 虚拟机状态检查超时时间（秒）
VM_STATUS_TIMEOUT = 10

# 虚拟机启动超时时间（秒）
VM_START_TIMEOUT = 60

# 虚拟机停止超时时间（秒）
VM_STOP_TIMEOUT = 30
```

### 日志配置
```python
# 日志文件路径
LOG_FILE = "vbox_monitor.log"

# Web日志文件路径
WEB_LOG_FILE = "vbox_web.log"

# 日志格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# 日志编码
LOG_ENCODING = "utf-8"
```

## 虚拟机状态说明

- **running**: 运行中
- **poweroff**: 已关闭
- **paused**: 已暂停
- **saved**: 已保存
- **aborted**: 异常终止
- **unknown**: 未知状态

## 日志文件

- `vbox_monitor.log`: 监控脚本日志
- `vbox_web.log`: Web应用日志

## 故障排除

### 1. VirtualBox未找到
确保VirtualBox已正确安装，系统会自动检测以下路径：
- Windows: `C:\Program Files\Oracle\VirtualBox\VBoxManage.exe`
- macOS: `/Applications/VirtualBox.app/Contents/MacOS/VBoxManage`
- Linux: `/usr/bin/VBoxManage`

如果自动检测失败，可以在配置文件中手动指定 `VBOXMANAGE_PATH`：
```python
VBOXMANAGE_PATH = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
```

### 2. 权限问题
确保运行脚本的用户有权限访问VirtualBox和虚拟机目录。

### 3. 端口被占用
如果5000端口被占用，可以修改配置文件中的 `WEB_PORT` 设置。

### 4. 虚拟机无法启动
检查虚拟机配置是否正确，确保虚拟机文件完整。

## 开发说明

### 项目结构
```
Monitor virtual machines/
├── vbox_monitor.py      # 核心监控脚本
├── vbox_web.py         # Web应用
├── start_monitor.py    # 启动脚本
├── config.py           # 配置文件
├── requirements.txt    # Python依赖
├── templates/          # HTML模板
│   └── index.html     # 主页面
└── README.md          # 说明文档
```

### 扩展功能
可以通过修改 `vbox_monitor.py` 来添加更多功能：
- 虚拟机快照管理
- 资源使用监控
- 网络配置管理
- 批量操作功能

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。 