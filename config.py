
# 登录配置
LOGIN_USERNAME = "admin"
LOGIN_PASSWORD = "123456"
LOGIN_REQUIRED = True
SESSION_SECRET_KEY = "vbox_monitor_secret_key_2024"
SESSION_TIMEOUT = 3600  # 会话超时时间（秒） 

# VirtualBox监控系统配置文件

# VirtualBox虚拟机目录路径
VBOX_DIR = r"D:\Users\wx\VirtualBox VMs"

# VirtualBox可执行文件路径
VBOXMANAGE_PATH = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"

# Web服务端口
WEB_PORT = 5000
# Web服务主机
WEB_HOST = "0.0.0.0"

# 日志级别
LOG_LEVEL = "DEBUG"
# 日志文件路径
LOG_FILE = "vbox_monitor.log"

# Web日志文件路径
WEB_LOG_FILE = "vbox_web.log"

# 监控日志文件路径
MONITOR_LOG_FILE = "monitor.log"

# 监控日志级别
MONITOR_LOG_LEVEL = "DEBUG"

# 监控日志格式
MONITOR_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

# 监控日志编码
MONITOR_LOG_ENCODING = "utf-8"

# 监控详细日志
MONITOR_VERBOSE_LOGGING = True

# 日志格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

# 日志编码
LOG_ENCODING = "utf-8"

# 是否启用详细日志
VERBOSE_LOGGING = True

# 是否启用API调试日志
ENABLE_API_DEBUG = True

# 是否启用前端调试日志
ENABLE_FRONTEND_DEBUG = True

# 是否启用命令执行调试日志
ENABLE_COMMAND_DEBUG = True

# 是否启用状态检查调试日志
ENABLE_STATUS_DEBUG = True

# 虚拟机状态检查超时时间（秒）
VM_STATUS_TIMEOUT = 15

# 虚拟机启动超时时间（秒）
VM_START_TIMEOUT = 60

# 虚拟机停止超时时间（秒）
VM_STOP_TIMEOUT = 30

# 扫描虚拟机超时时间（秒）
SCAN_VMS_TIMEOUT = 30

# 获取虚拟机信息超时时间（秒）
VM_INFO_TIMEOUT = 15

# 是否在启动时自动扫描虚拟机
AUTO_SCAN_ON_START = True

# 是否在监控时显示详细状态
SHOW_DETAILED_STATUS = True

# 监控线程是否为守护线程
MONITOR_THREAD_DAEMON = True

# 是否启用Web界面
ENABLE_WEB_INTERFACE = True

# 是否启用API接口
ENABLE_API_INTERFACE = True

# 是否启用自动启动功能
ENABLE_AUTO_START = True

# 是否启用详细错误信息
SHOW_DETAILED_ERRORS = True

# 虚拟机状态映射（中文显示）
VM_STATUS_MAPPING = {
    'running': '运行中',
    'poweroff': '已关闭',
    'paused': '已暂停',
    'saved': '已保存',
    'aborted': '异常终止',
    'unknown': '未知状态'
}

# 虚拟机状态颜色映射
VM_STATUS_COLORS = {
    'running': 'success',
    'poweroff': 'secondary',
    'paused': 'warning',
    'saved': 'info',
    'aborted': 'danger',
    'unknown': 'dark'
}

# 虚拟机状态图标映射
VM_STATUS_ICONS = {
    'running': 'fas fa-play',
    'poweroff': 'fas fa-stop',
    'paused': 'fas fa-pause',
    'saved': 'fas fa-save',
    'aborted': 'fas fa-exclamation-triangle',
    'unknown': 'fas fa-question'
}

# VirtualBox可执行文件常见路径
VBOXMANAGE_POSSIBLE_PATHS = [
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
    "/usr/bin/VBoxManage",
    "/usr/local/bin/VBoxManage",
    "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
]

# 是否启用自动检测VirtualBox路径
AUTO_DETECT_VBOXMANAGE = True

# VirtualBox启动类型
VBOX_START_TYPE = "headless"

# 监控虚拟机状态功能
ENABLE_VM_STATUS_MONITORING = True



# 是否在Web界面显示监控虚拟机状态按钮
SHOW_VM_STATUS_MONITOR_BUTTON = True

# 母盘虚拟机配置
MASTER_VM_EXCEPTIONS = [
    "TemplateVM",
    "BaseVM", 
    "MasterVM",
    "Template",
    "Base"
]

# 是否启用母盘虚拟机例外功能
ENABLE_MASTER_VM_EXCEPTIONS = True

# 选中的虚拟机目录配置
SELECTED_VM_DIRECTORIES = [
    r"D:\Users\wx\VirtualBox VMs"
]

# 是否启用多目录监控
ENABLE_MULTI_DIRECTORY_MONITORING = True

# 是否在Web界面显示目录选择功能
SHOW_DIRECTORY_SELECTION = True

# 监控配置
ENABLE_REALTIME_STATUS_MONITORING = True



# 是否在状态变化时发送通知
ENABLE_STATUS_CHANGE_NOTIFICATIONS = True

# 监控按钮配置
MONITOR_BUTTON_TEXT = "监控虚拟机状态"

# 监控按钮图标
MONITOR_BUTTON_ICON = "fas fa-eye"

# 监控按钮颜色类
MONITOR_BUTTON_COLOR = "btn-primary"

# 是否显示监控状态指示器
SHOW_MONITOR_STATUS_INDICATOR = True

# 监控状态指示器颜色
MONITOR_STATUS_INDICATOR_COLORS = {
    'active': 'success',
    'inactive': 'secondary',
    'error': 'danger'
}

# 自动刷新按钮开启状态（对应页面上的自动刷新开关）
AUTO_REFRESH_BUTTON_ENABLED = False

# 自动刷新下拉时间数值（对应页面上的时间选择器）
AUTO_REFRESH_INTERVAL_VALUE = 600

# 自动监控按钮开启状态（对应页面上的自动监控开关）
AUTO_MONITOR_BUTTON_ENABLED = True

# 自动监控下拉时间数值（对应页面上的监控时间选择器）
AUTO_MONITOR_INTERVAL_VALUE = 30

# 自启动虚拟机按钮开启状态（对应页面上的自启动开关）
AUTO_START_VM_BUTTON_ENABLED = True

# 是否启用自动启动已停止的虚拟机功能
AUTO_START_STOPPED_VMS = True

#  自动启动已停止的虚拟机数量，建议不要超出物理内存90%，总量/单个虚拟机内存大小
AUTO_START_STOPPED_NUM = 2

# 自动删除虚拟机配置
AUTO_DELETE_ENABLED = False
AUTO_DELETE_MAX_COUNT = 10
AUTO_DELETE_BACKUP_DIR = "delete_bak"


