#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VirtualBox虚拟机监控系统启动脚本
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# 导入console_logger用于控制台输出
try:
    from vbox_monitor import console_logger
except ImportError:
    # 如果无法导入，创建一个简单的控制台输出函数
    def console_logger():
        class SimpleLogger:
            def info(self, msg):
                print(msg)
            def warning(self, msg):
                print(f"警告: {msg}")
            def error(self, msg):
                print(f"错误: {msg}")
        return SimpleLogger()
    console_logger = console_logger()

def check_virtualbox():
    """检查VirtualBox是否已安装"""
    try:
        # 尝试运行VBoxManage --version
        result = subprocess.run(['VBoxManage', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✓ VirtualBox已安装，版本: {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # 检查常见安装路径
    possible_paths = [
        r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
        r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
        "/usr/bin/VBoxManage",
        "/usr/local/bin/VBoxManage",
        "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✓ 找到VirtualBox: {path}")
            return True
    
    print("✗ 未找到VirtualBox，请确保已正确安装")
    return False

# 移除VirtualBox服务健康检查函数

def check_python_dependencies():
    """检查Python依赖"""
    required_packages = ['flask']
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} 未安装")
    
    if missing_packages:
        print(f"\n请安装缺失的依赖包:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def print_initial_config():
    """打印初始配置状态"""
    try:
        from config import (
            AUTO_REFRESH_BUTTON_ENABLED, AUTO_REFRESH_INTERVAL_VALUE,
            AUTO_MONITOR_BUTTON_ENABLED, AUTO_MONITOR_INTERVAL_VALUE,
            AUTO_START_VM_BUTTON_ENABLED, AUTO_START_STOPPED_NUM,
            AUTO_DELETE_ENABLED, AUTO_DELETE_MAX_COUNT
        )
        
        print("\n=== 当前配置状态 ===")
        
        # 自动刷新配置
        if AUTO_REFRESH_BUTTON_ENABLED:
            console_logger.info(f"自动刷新: 已启用，间隔 {AUTO_REFRESH_INTERVAL_VALUE} 秒")
        else:
            console_logger.info("自动刷新: 已禁用")
        
        # 自动监控配置
        if AUTO_MONITOR_BUTTON_ENABLED:
            console_logger.info(f"自动监控: 已启用，间隔 {AUTO_MONITOR_INTERVAL_VALUE} 秒")
        else:
            console_logger.info("自动监控: 已禁用")
        
        # 自启动虚拟机配置
        if AUTO_START_VM_BUTTON_ENABLED:
            console_logger.info(f"自启动虚拟机: 已启用，启动数量 {AUTO_START_STOPPED_NUM}")
        else:
            console_logger.info("自启动虚拟机: 已禁用")
        
        # 自动删除虚拟机配置
        if AUTO_DELETE_ENABLED:
            console_logger.info(f"自动删除虚拟机: 已启用，启动次数限制 {AUTO_DELETE_MAX_COUNT}")
        else:
            console_logger.info("自动删除虚拟机: 已禁用")
        
        print("==================\n")
        
    except ImportError as e:
        print(f"无法读取配置文件: {e}")
    except Exception as e:
        print(f"读取配置状态失败: {e}")

def create_config():
    """创建配置文件"""
    config_content = '''# VirtualBox监控系统配置文件

# VirtualBox虚拟机目录路径
# 留空则使用默认路径
VBOX_DIR = ""

# VirtualBox可执行文件路径
# 留空则自动检测
VBOXMANAGE_PATH = ""

# 监控间隔（秒）- 使用配置文件中的AUTO_MONITOR_INTERVAL_VALUE
MONITOR_INTERVAL = 30

# Web服务端口
WEB_PORT = 5000

# Web服务主机
WEB_HOST = "0.0.0.0"

# 日志级别
LOG_LEVEL = "INFO"

# 自动启动已停止的虚拟机
AUTO_START_STOPPED_VMS = True

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
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# 日志编码
LOG_ENCODING = "utf-8"

# 虚拟机状态检查超时时间（秒）
VM_STATUS_TIMEOUT = 10

# 虚拟机启动超时时间（秒）
VM_START_TIMEOUT = 60

# 虚拟机停止超时时间（秒）
VM_STOP_TIMEOUT = 30

# 扫描虚拟机超时时间（秒）
SCAN_VMS_TIMEOUT = 10

# 获取虚拟机信息超时时间（秒）
VM_INFO_TIMEOUT = 10

# 是否启用详细日志
VERBOSE_LOGGING = True

# 是否在启动时自动扫描虚拟机
AUTO_SCAN_ON_START = True

# 是否在监控时显示详细状态
SHOW_DETAILED_STATUS = True

# Web界面自动刷新间隔（秒）- 使用配置文件中的AUTO_REFRESH_INTERVAL_VALUE
AUTO_REFRESH_INTERVAL_VALUE = 600

# 监控线程是否为守护线程
MONITOR_THREAD_DAEMON = True

# 是否启用Web界面
ENABLE_WEB_INTERFACE = True

# 是否启用API接口
ENABLE_API_INTERFACE = True

# 是否启用自动监控功能
ENABLE_AUTO_MONITORING = True

# 是否启用自动启动功能
ENABLE_AUTO_START = True

# 是否启用详细错误信息
SHOW_DETAILED_ERRORS = True

# VirtualBox可执行文件常见路径
VBOXMANAGE_POSSIBLE_PATHS = [
    r"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe",
    r"C:\\Program Files (x86)\\Oracle\\VirtualBox\\VBoxManage.exe",
    "/usr/bin/VBoxManage",
    "/usr/local/bin/VBoxManage",
    "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
]

# 是否启用自动检测VirtualBox路径
AUTO_DETECT_VBOXMANAGE = True

# VirtualBox启动类型
# 可选值: headless, gui, sdl
VBOX_START_TYPE = "headless"

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
'''
    
    config_file = Path(__file__).parent / "config.py"
    if not config_file.exists():
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        print("✓ 配置文件已创建: config.py")
    else:
        print("✓ 配置文件已存在: config.py")

def main():
    """主函数"""
    print("=== VirtualBox虚拟机监控系统启动检查 ===")
    print()
    
    # 检查VirtualBox
    if not check_virtualbox():
        print("\n请先安装VirtualBox，然后重新运行此脚本")
        return False
    
    print()
    
    # 移除VirtualBox服务状态检查
    print("\n✅ 系统将直接启动监控")
    
    print()
    
    # 检查Python依赖
    if not check_python_dependencies():
        print("\n请安装缺失的依赖包后重新运行此脚本")
        return False
    
    print()
    
    # 创建配置文件
    create_config()
    
    # 打印初始配置状态
    print_initial_config()
    
    print("=== 启动监控系统 ===")
    
    # 启动Web应用
    try:
        from vbox_web import app
        from config import WEB_HOST, WEB_PORT
        print("✓ 监控系统启动成功")
        print(f"🌐 访问地址: http://localhost:{WEB_PORT}")
        print("按 Ctrl+C 停止服务")
        
        app.run(host=WEB_HOST, port=WEB_PORT, debug=False)
        
    except ImportError as e:
        print(f"✗ 导入模块失败: {e}")
        return False
    except KeyboardInterrupt:
        print("\n✓ 监控系统已停止")
        return True
    except Exception as e:
        print(f"✗ 启动失败: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 