# VirtualBox虚拟机监控系统

<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/4583b2e4-31e8-400c-9417-c736671e9ce0" />



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

# 虚拟机启动重试间隔时间（秒）
VM_START_RETRY_INTERVAL = 5

# 虚拟机启动最大重试次数
VM_START_MAX_RETRIES = 3
```

### 虚拟机重试机制

当虚拟机启动失败时，系统会按照配置文件中的设置进行重试：

- **重试间隔时间**: 5秒（可配置）
- **最大重试次数**: 3次（可配置）
- **重试日志**: 每次重试前会显示等待时间

重试过程示例：
```
2025-08-05 11:25:51,013 - WARNING - 启动虚拟机 centos7-009 失败，将进行第 1 次重试
2025-08-05 11:25:51,013 - INFO - 第 1 次重试启动虚拟机: centos7-009
2025-08-05 11:25:51,013 - INFO - 等待 5 秒后进行重试...
2025-08-05 11:25:56,015 - INFO - 正在启动虚拟机: centos7-009
2025-08-05 11:25:56,124 - WARNING - 启动虚拟机 centos7-009 失败，将进行第 2 次重试
```

### 日志配置
```python
# 生成带时间戳的日志文件名
from datetime import datetime

def generate_log_filename(prefix):
    """生成带时间戳的日志文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"log/{prefix}_{timestamp}.log"

# 日志文件路径
LOG_FILE = generate_log_filename("vbox_monitor")

# Web日志文件路径
WEB_LOG_FILE = generate_log_filename("vbox_web")

# 监控日志文件路径
MONITOR_LOG_FILE = generate_log_filename("monitor")

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

日志文件统一存储在项目目录的 `log/` 文件夹中，按照启动时间自动命名，格式为：`log/{前缀}_{YYYYMMDD_HHMMSS}.log`

- `log/vbox_monitor_{timestamp}.log`: 监控脚本日志
- `log/vbox_web_{timestamp}.log`: Web应用日志  
- `log/monitor_{timestamp}.log`: 监控专用日志

例如：
- `log/vbox_monitor_20250805_110025.log`
- `log/vbox_web_20250805_110025.log`
- `log/monitor_20250805_110025.log`

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
