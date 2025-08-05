#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VirtualBox虚拟机监控脚本
功能：
1. 扫描指定目录下的VirtualBox虚拟机
2. 检查虚拟机状态
3. 自动启动关闭的虚拟机
4. 提供Web API接口
"""

import os
import subprocess
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading
try:
    import schedule
except ImportError:
    # 如果没有安装schedule模块，创建一个简单的替代
    class SimpleSchedule:
        def every(self, interval):
            return self
        def seconds(self):
            return self
        def do(self, func):
            return self
        def run_pending(self):
            pass
    schedule = SimpleSchedule()

# 导入配置文件
try:
    from config import *
except ImportError:
    # 如果配置文件不存在，使用默认配置
    VBOX_DIR = ""
    VBOXMANAGE_PATH = ""
    VBOXMANAGE_POSSIBLE_PATHS = [
        r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
        r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
        "/usr/bin/VBoxManage",
        "/usr/local/bin/VBoxManage",
        "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
    ]
    AUTO_DETECT_VBOXMANAGE = True
    VBOX_START_TYPE = "headless"
    LOG_LEVEL = "INFO"
    # 生成按天的日志文件名
    from datetime import datetime
    
    def generate_daily_log_filename(prefix):
        """生成按天的日志文件名"""
        date_str = datetime.now().strftime("%Y%m%d")
        return f"log/{prefix}_{date_str}.log"
    
    LOG_FILE = generate_daily_log_filename("vbox_monitor")
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
    LOG_ENCODING = "utf-8"
    VM_STATUS_TIMEOUT = 15
    VM_START_TIMEOUT = 60
    VM_STOP_TIMEOUT = 30
    SCAN_VMS_TIMEOUT = 30
    VM_INFO_TIMEOUT = 15
    VERBOSE_LOGGING = True
    AUTO_START_STOPPED_VMS = True
    MONITOR_THREAD_DAEMON = True

# 配置主日志 - 只写入文件，控制台不输出
log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding=LOG_ENCODING)
    ]
)
logger = logging.getLogger(__name__)

# 配置监控专用日志
try:
    from config import MONITOR_LOG_FILE, MONITOR_LOG_LEVEL, MONITOR_LOG_FORMAT, MONITOR_LOG_ENCODING, MONITOR_VERBOSE_LOGGING
    monitor_log_level = getattr(logging, MONITOR_LOG_LEVEL.upper(), logging.DEBUG)
    
    # 创建监控日志处理器 - 只写入文件
    monitor_handler = logging.FileHandler(MONITOR_LOG_FILE, encoding=MONITOR_LOG_ENCODING)
    monitor_handler.setLevel(monitor_log_level)
    
    # 创建监控日志格式化器
    monitor_formatter = logging.Formatter(MONITOR_LOG_FORMAT)
    monitor_handler.setFormatter(monitor_formatter)
    
    # 创建监控日志记录器
    monitor_logger = logging.getLogger('monitor')
    monitor_logger.setLevel(monitor_log_level)
    monitor_logger.addHandler(monitor_handler)
    monitor_logger.propagate = False  # 防止重复输出
    
    if MONITOR_VERBOSE_LOGGING:
        monitor_logger.setLevel(logging.DEBUG)
        monitor_logger.debug("监控日志系统初始化完成")
    
    # 创建控制台日志记录器 - 只记录前台页面操作
    console_logger = logging.getLogger('console')
    console_logger.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建控制台格式化器
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    
    # 添加控制台处理器
    console_logger.addHandler(console_handler)
    console_logger.propagate = False
    
except ImportError:
    # 如果监控日志配置不存在，使用默认配置
    monitor_logger = logger
    monitor_logger.warning("监控日志配置未找到，使用主日志记录器")

# 设置详细调试日志
if VERBOSE_LOGGING:
    logger.setLevel(logging.DEBUG)
    logger.debug("启用详细调试日志")

class VirtualBoxMonitor:
    def __init__(self, vbox_dir: str = None):
        """
        初始化VirtualBox监控器
        
        Args:
            vbox_dir: VirtualBox虚拟机目录路径
        """
        # 使用配置文件中的目录，如果为空则使用默认路径
        self.vbox_dir = vbox_dir or VBOX_DIR or self._get_default_vbox_dir()
        self.vboxmanage_path = self._find_vboxmanage()
        self.vms = {}  # 存储虚拟机信息
        self.monitoring = False
        self.monitor_thread = None
        self.vm_exceptions = {}  # 存储虚拟机异常状态
        self.auto_start_enabled = True  # 默认启用自动启动
        self.last_monitor_results = []  # 存储最后一次监控结果
        self.monitor_start_time = None  # 监控启动时间
        
        # 状态变化检测相关
        self.last_vm_status = {}  # 存储上次的虚拟机状态
        self.status_change_detected = False  # 状态变化标志
        
        # 虚拟机启动次数管理
        self.vm_config_file = "vm.config"
        self.vm_start_counts = {}  # 存储虚拟机启动次数
        self.load_vm_config()
        
        logger.info(f"VirtualBox监控器初始化完成")
        logger.info(f"虚拟机目录: {self.vbox_dir}")
        logger.info(f"VBoxManage路径: {self.vboxmanage_path}")
        
        # 监控日志记录
        monitor_logger.info(f"VirtualBox监控器初始化完成")
        monitor_logger.info(f"虚拟机目录: {self.vbox_dir}")
        monitor_logger.info(f"VBoxManage路径: {self.vboxmanage_path}")
        logger.info(f"日志级别: {LOG_LEVEL}")
        logger.info(f"启动类型: {VBOX_START_TYPE}")
        
        # 移除启动时VirtualBox服务状态检查
    
    def _get_default_vbox_dir(self) -> str:
        """获取默认VirtualBox目录"""
        # Windows默认路径
        if os.name == 'nt':
            default_dir = os.path.expanduser(r"~\VirtualBox VMs")
            # 如果默认目录不存在，尝试其他可能的路径
            if not os.path.exists(default_dir):
                # 尝试从VBoxManage获取默认机器文件夹
                try:
                    result = subprocess.run(
                        [self.vboxmanage_path, 'list', 'systemproperties'],
                        capture_output=True, timeout=15
                    )
                    if result.returncode == 0:
                        try:
                            stdout = result.stdout.decode('utf-8', errors='ignore')
                        except UnicodeDecodeError:
                            try:
                                stdout = result.stdout.decode('gbk', errors='ignore')
                            except UnicodeDecodeError:
                                stdout = result.stdout.decode('latin-1', errors='ignore')
                        
                        lines = stdout.strip().split('\n')
                        for line in lines:
                            if 'Default machine folder:' in line:
                                default_dir = line.split(':', 1)[1].strip()
                                logger.info(f"从VBoxManage获取到默认机器文件夹: {default_dir}")
                                break
                except Exception as e:
                    logger.warning(f"无法从VBoxManage获取默认机器文件夹: {e}")
            
            return default_dir
        # macOS默认路径
        elif os.name == 'posix' and os.uname().sysname == 'Darwin':
            return os.path.expanduser("~/VirtualBox VMs")
        # Linux默认路径
        else:
            return os.path.expanduser("~/VirtualBox VMs")
    
    def _find_vboxmanage(self) -> str:
        """查找VBoxManage可执行文件"""
        # 如果配置文件中指定了具体路径，优先使用
        if VBOXMANAGE_PATH and VBOXMANAGE_PATH != "auto" and os.path.exists(VBOXMANAGE_PATH):
            logger.info(f"使用配置文件中指定的VBoxManage路径: {VBOXMANAGE_PATH}")
            return VBOXMANAGE_PATH
        
        # 如果设置为"auto"或未指定，进行自动检测
        logger.info("开始自动检测VBoxManage路径...")
        
        # 首先尝试从PATH中查找
        try:
            result = subprocess.run(['VBoxManage', '--version'], 
                                  capture_output=True, timeout=15)
            if result.returncode == 0:
                logger.info("从PATH中找到VBoxManage")
                return 'VBoxManage'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 使用配置文件中的可能路径列表
        possible_paths = VBOXMANAGE_POSSIBLE_PATHS
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"找到VBoxManage: {path}")
                return path
        
        # 如果启用自动检测，尝试更多可能的路径
        if AUTO_DETECT_VBOXMANAGE:
            # Windows系统额外检查
            if os.name == 'nt':
                additional_paths = [
                    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
                    r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
                    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
                    r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe"
                ]
                for path in additional_paths:
                    if os.path.exists(path):
                        logger.info(f"在Windows路径中找到VBoxManage: {path}")
                        return path
            
            # macOS系统额外检查
            elif os.name == 'posix' and hasattr(os, 'uname') and os.uname().sysname == 'Darwin':
                additional_paths = [
                    "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage",
                    "/usr/local/bin/VBoxManage",
                    "/opt/homebrew/bin/VBoxManage"
                ]
                for path in additional_paths:
                    if os.path.exists(path):
                        logger.info(f"在macOS路径中找到VBoxManage: {path}")
                        return path
            
            # Linux系统额外检查
            else:
                additional_paths = [
                    "/usr/bin/VBoxManage",
                    "/usr/local/bin/VBoxManage",
                    "/opt/VirtualBox/VBoxManage"
                ]
                for path in additional_paths:
                    if os.path.exists(path):
                        logger.info(f"在Linux路径中找到VBoxManage: {path}")
                        return path
        
        # 如果都找不到，提供详细的错误信息
        error_msg = "未找到VBoxManage，请确保VirtualBox已正确安装。\n"
        error_msg += "已检查的路径:\n"
        for path in possible_paths:
            error_msg += f"  - {path}\n"
        error_msg += "请检查VirtualBox是否正确安装，或在配置文件中手动指定VBOXMANAGE_PATH"
        
        raise FileNotFoundError(error_msg)
    
    def _check_vbox_service(self) -> bool:
        """
        检查VirtualBox服务是否响应
        
        Returns:
            bool: 服务是否响应
        """
        try:
            # 从配置文件获取超时时间
            from config import VM_STATUS_TIMEOUT
            service_timeout = min(VM_STATUS_TIMEOUT, 10)  # 服务检查使用较短超时
            
            logger.debug("检查VirtualBox服务响应性...")
            result = subprocess.run(
                [self.vboxmanage_path, '--version'],
                capture_output=True, timeout=service_timeout
            )
            
            if result.returncode == 0:
                try:
                    version = result.stdout.decode('utf-8', errors='ignore').strip()
                    logger.debug(f"VirtualBox服务正常，版本: {version}")
                    return True
                except:
                    logger.debug("VirtualBox服务正常，但无法解析版本信息")
                    return True
            else:
                logger.warning("VirtualBox服务响应异常")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("VirtualBox服务响应超时")
            return False
        except Exception as e:
            logger.error(f"检查VirtualBox服务时出错: {e}")
            return False

    def scan_vms(self, scan_status: bool = False) -> List[Dict]:
        """
        递归扫描VBOX_DIR目录中的虚拟机，支持分组目录结构
        默认只扫描虚拟机文件，不扫描状态以提高性能
        
        Args:
            scan_status: 是否扫描虚拟机状态，默认False以提高性能
            
        Returns:
            虚拟机信息列表
        """
        vms = []
        
        logger.info(f"开始递归扫描VBOX_DIR目录: {self.vbox_dir}")
        
        # 直接使用基于文件的扫描方式，不再依赖VBoxManage服务
        logger.info("使用基于文件的扫描方式，不依赖VBoxManage服务")
        
        if not os.path.exists(self.vbox_dir):
            logger.error(f"VBOX_DIR目录不存在: {self.vbox_dir}")
            return vms
        
        try:
            # 递归扫描VBOX_DIR目录中的虚拟机文件
            vbox_dir_abs = os.path.abspath(self.vbox_dir)
            logger.debug(f"VBOX_DIR绝对路径: {vbox_dir_abs}")
            
            # 递归扫描函数
            def scan_directory_recursive(directory_path, depth=0):
                """递归扫描目录中的虚拟机"""
                local_vms = []
                
                # 限制递归深度，避免无限递归
                if depth > 10:
                    logger.warning(f"递归深度超过限制，跳过目录: {directory_path}")
                    return local_vms
                
                try:
                    for item in os.listdir(directory_path):
                        item_path = os.path.join(directory_path, item)
                        
                        # 检查是否是目录
                        if os.path.isdir(item_path):
                            # 查找.vbox文件
                            vbox_files = [f for f in os.listdir(item_path) if f.endswith('.vbox')]
                            
                            if vbox_files:
                                # 找到.vbox文件，这是一个虚拟机
                                vm_name = item
                                vbox_file = os.path.join(item_path, vbox_files[0])
                                
                                logger.debug(f"发现虚拟机目录: {item_path}")
                                logger.debug(f"虚拟机文件: {vbox_file}")
                                
                                # 直接生成基于名称的UUID，不再从VBoxManage获取
                                import hashlib
                                hash_object = hashlib.md5(vm_name.encode())
                                uuid = hash_object.hexdigest()
                                vm_uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:32]}"
                                
                                vm_info = {
                                    'name': vm_name,
                                    'uuid': vm_uuid,
                                    'path': vbox_file,
                                    'status': 'unknown',
                                    'last_check': datetime.now().isoformat()
                                }
                                
                                # 尝试获取虚拟机状态，如果失败则设为unknown
                                try:
                                    status = self.get_vm_status(vm_name)
                                    vm_info['status'] = status
                                    logger.debug(f"获取虚拟机 {vm_name} 状态: {status}")
                                except Exception as e:
                                    logger.warning(f"获取虚拟机 {vm_name} 状态失败: {e}")
                                    vm_info['status'] = 'unknown'
                                
                                local_vms.append(vm_info)
                                logger.info(f"发现VBOX_DIR中的虚拟机: {vm_name} (生成UUID: {vm_uuid})")
                            else:
                                # 如果没有找到.vbox文件，递归扫描子目录
                                logger.debug(f"目录 {item_path} 中没有找到.vbox文件，递归扫描子目录")
                                sub_vms = scan_directory_recursive(item_path, depth + 1)
                                local_vms.extend(sub_vms)
                        else:
                            logger.debug(f"跳过非目录项: {item_path}")
                
                except Exception as e:
                    logger.error(f"扫描目录 {directory_path} 时出错: {e}")
                
                return local_vms
            
            # 开始递归扫描
            vms = scan_directory_recursive(self.vbox_dir)
            
        except Exception as e:
            logger.error(f"扫描VBOX_DIR目录时出错: {e}")
            monitor_logger.error(f"扫描VBOX_DIR目录时出错: {e}")
        
        logger.info(f"扫描完成，在VBOX_DIR中发现 {len(vms)} 个虚拟机")
        
        # 添加详细的扫描结果信息
        if vms:
            logger.info("扫描到的虚拟机列表:")
            for vm in vms:
                logger.info(f"  - {vm['name']} (UUID: {vm['uuid']}, 路径: {vm['path']})")
        else:
            logger.warning("未在VBOX_DIR中发现任何虚拟机")
            logger.info("请检查以下可能的原因:")
            logger.info("1. VBOX_DIR路径是否正确")
            logger.info("2. 该目录中是否有虚拟机文件(.vbox)")
            logger.info("3. 虚拟机是否已正确注册到VirtualBox")
            monitor_logger.warning("未在VBOX_DIR中发现任何虚拟机")
        
        return vms
    
    def scan_vm_status_async(self, vms: List[Dict]) -> List[Dict]:
        """
        异步扫描虚拟机状态，提高性能（简化版本）
        
        Args:
            vms: 虚拟机列表
            
        Returns:
            更新状态后的虚拟机列表
        """
        logger.info(f"开始异步扫描 {len(vms)} 个虚拟机的状态")
        
        # 简化版本：只更新检查时间，不获取实际状态
        for vm in vms:
            vm['last_check'] = datetime.now().isoformat()
            # 保持状态为unknown，避免超时问题
            vm['status'] = 'unknown'
        
        logger.info(f"异步状态扫描完成，共处理 {len(vms)} 个虚拟机")
        return vms
    
    def _get_vm_path(self, vm_name: str) -> str:
        """获取虚拟机文件路径（支持递归查找）"""
        # 首先尝试从VBoxManage获取虚拟机信息
        try:
            result = subprocess.run(
                [self.vboxmanage_path, 'showvminfo', vm_name, '--machinereadable'],
                capture_output=True, timeout=15
            )
            if result.returncode == 0:
                try:
                    stdout = result.stdout.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stdout = result.stdout.decode('gbk', errors='ignore')
                    except UnicodeDecodeError:
                        stdout = result.stdout.decode('latin-1', errors='ignore')
                
                lines = stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('CfgFile='):
                        cfg_file = line.split('=', 1)[1].strip('"')
                        if os.path.exists(cfg_file):
                            return cfg_file
        except Exception as e:
            logger.debug(f"无法从VBoxManage获取虚拟机 {vm_name} 的配置文件路径: {e}")
        
        # 递归查找虚拟机目录
        def find_vm_directory(base_dir, target_vm_name, depth=0):
            """递归查找虚拟机目录"""
            if depth > 10:  # 限制递归深度
                return None
            
            try:
                for item in os.listdir(base_dir):
                    item_path = os.path.join(base_dir, item)
                    
                    if os.path.isdir(item_path):
                        # 检查是否是目标虚拟机目录
                        if item == target_vm_name:
                            # 检查是否包含.vbox文件
                            vbox_files = [f for f in os.listdir(item_path) if f.endswith('.vbox')]
                            if vbox_files:
                                logger.debug(f"找到虚拟机目录: {item_path}")
                                return item_path
                        
                        # 递归搜索子目录
                        sub_result = find_vm_directory(item_path, target_vm_name, depth + 1)
                        if sub_result:
                            return sub_result
            except Exception as e:
                logger.debug(f"搜索目录 {base_dir} 时出错: {e}")
            
            return None
        
        # 首先尝试直接路径
        vm_dir = os.path.join(self.vbox_dir, vm_name)
        vbox_file = os.path.join(vm_dir, f"{vm_name}.vbox")
        
        if os.path.exists(vbox_file):
            logger.debug(f"找到虚拟机文件: {vbox_file}")
            return vbox_file
        
        # 如果直接路径不存在，递归查找
        logger.debug(f"直接路径不存在，开始递归查找虚拟机 {vm_name}")
        found_dir = find_vm_directory(self.vbox_dir, vm_name)
        
        if found_dir:
            # 查找.vbox文件
            vbox_files = [f for f in os.listdir(found_dir) if f.endswith('.vbox')]
            if vbox_files:
                vbox_file = os.path.join(found_dir, vbox_files[0])
                logger.debug(f"递归找到虚拟机文件: {vbox_file}")
                return vbox_file
            else:
                logger.debug(f"找到虚拟机目录但没有.vbox文件: {found_dir}")
                return found_dir
        else:
            logger.warning(f"未找到虚拟机 {vm_name} 的目录")
            return vm_dir  # 返回默认路径
    
    def _get_vm_uuid_from_vboxmanage(self, vm_name: str) -> str:
        """生成基于虚拟机名称的UUID，不再从VBoxManage获取"""
        import hashlib
        hash_object = hashlib.md5(vm_name.encode())
        uuid = hash_object.hexdigest()
        vm_uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:32]}"
        logger.debug(f"为虚拟机 {vm_name} 生成UUID: {vm_uuid}")
        return vm_uuid
    
    def get_vm_status(self, vm_name: str) -> str:
        """
        获取虚拟机状态（简化版本，移除服务检测）
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            虚拟机状态: running, poweroff, paused, saved, aborted, unknown
        """
        
        try:
            # 从配置文件获取超时时间
            from config import VM_STATUS_TIMEOUT
            timeout_value = VM_STATUS_TIMEOUT
            
            logger.debug(f"获取虚拟机 {vm_name} 状态 (超时: {timeout_value}秒)")
            result = subprocess.run(
                [self.vboxmanage_path, 'showvminfo', vm_name, '--machinereadable'],
                capture_output=True, timeout=timeout_value
            )
            
            if result.returncode == 0:
                try:
                    stdout = result.stdout.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    stdout = result.stdout.decode('gbk', errors='ignore')
                
                lines = stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('VMState='):
                        status = line.split('=', 1)[1].strip().strip('"')
                        logger.debug(f"虚拟机 {vm_name} 状态: {status}")
                        
                        # 状态映射
                        status_mapping = {
                            'running': 'running',
                            'poweroff': 'poweroff', 
                            'paused': 'paused',
                            'saved': 'saved',
                            'aborted': 'aborted',
                            'starting': 'running',
                            'stopping': 'poweroff',
                            'saving': 'saved',
                            'restoring': 'running'
                        }
                        
                        return status_mapping.get(status, 'unknown')
                
                # 如果没有找到状态，尝试检查运行列表
                try:
                    from config import VM_STATUS_TIMEOUT
                    running_timeout = min(VM_STATUS_TIMEOUT // 2, 5)  # 使用较短的超时时间
                    running_result = subprocess.run(
                        [self.vboxmanage_path, 'list', 'runningvms'],
                        capture_output=True, timeout=running_timeout
                    )
                    if running_result.returncode == 0:
                        try:
                            running_stdout = running_result.stdout.decode('utf-8', errors='ignore')
                        except UnicodeDecodeError:
                            running_stdout = running_result.stdout.decode('gbk', errors='ignore')
                        
                        if vm_name in running_stdout:
                            return 'running'
                except:
                    pass
                
                return 'unknown'
            else:
                logger.warning(f"获取虚拟机 {vm_name} 状态失败，返回码: {result.returncode}")
                return 'unknown'
                
        except subprocess.TimeoutExpired:
            logger.warning(f"获取虚拟机 {vm_name} 状态超时")
            return 'unknown'
        except Exception as e:
            logger.warning(f"获取虚拟机 {vm_name} 状态时出错: {e}")
            return 'unknown'
    
    def start_vm(self, vm_name: str) -> bool:
        """
        启动虚拟机（简化版本，移除服务检测）
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            是否成功启动
        """
        
        try:
            console_logger.info(f"正在启动虚拟机: {vm_name}")
            result = subprocess.run(
                [self.vboxmanage_path, 'startvm', vm_name, '--type', VBOX_START_TYPE],
                capture_output=True, timeout=60  # 减少超时时间
            )
            
            # 简化编码处理
            try:
                stderr = result.stderr.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                stderr = result.stderr.decode('gbk', errors='ignore')
            
            if result.returncode == 0:
                logger.info(f"虚拟机 {vm_name} 启动成功")
                self.clear_vm_exception(vm_name)
                # 增加启动次数
                self.increment_vm_start_count(vm_name)
                
                # 检查是否达到删除阈值
                if self.auto_delete_enabled and self.vm_start_counts.get(vm_name, 0) >= self.max_start_count:
                    logger.warning(f"虚拟机 {vm_name} 启动次数达到删除阈值 {self.max_start_count}，准备自动删除")
                    # 异步执行删除操作，避免阻塞启动流程
                    import threading
                    delete_thread = threading.Thread(target=self.auto_delete_vm, args=(vm_name,))
                    delete_thread.daemon = True
                    delete_thread.start()
                    logger.info(f"虚拟机 {vm_name} 自动删除任务已启动")
                
                return True
            else:
                error_msg = f"启动失败: {stderr}"
                logger.error(f"虚拟机 {vm_name} {error_msg}")
                self.mark_vm_exception(vm_name, 'start', error_msg)
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"启动虚拟机 {vm_name} 超时")
            return False
        except Exception as e:
            logger.error(f"启动虚拟机 {vm_name} 时出错: {e}")
            return False
    
    def stop_vm(self, vm_name: str) -> bool:
        """
        停止虚拟机（简化版本，移除服务检测）
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            是否成功停止
        """
        
        try:
            console_logger.info(f"正在停止虚拟机: {vm_name}")
            logger.info(f"🔄 执行停止命令: {self.vboxmanage_path} controlvm {vm_name} poweroff")
            monitor_logger.info(f"🔄 执行停止命令: {self.vboxmanage_path} controlvm {vm_name} poweroff")
            
            # 强制刷新日志输出
            import sys
            sys.stdout.flush()
            
            result = subprocess.run(
                [self.vboxmanage_path, 'controlvm', vm_name, 'poweroff'],
                capture_output=True, timeout=30  # 保持30秒超时
            )
            
            logger.info(f"🔄 停止命令执行完成，返回码: {result.returncode}")
            monitor_logger.info(f"🔄 停止命令执行完成，返回码: {result.returncode}")
            
            # 强制刷新日志输出
            sys.stdout.flush()
            
            # 简化编码处理
            try:
                stderr = result.stderr.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                stderr = result.stderr.decode('gbk', errors='ignore')
            
            if result.returncode == 0:
                logger.info(f"虚拟机 {vm_name} 停止成功")
                self.clear_vm_exception(vm_name)
                return True
            else:
                error_msg = f"停止失败: {stderr}"
                logger.error(f"虚拟机 {vm_name} {error_msg}")
                self.mark_vm_exception(vm_name, 'stop', error_msg)
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"停止虚拟机 {vm_name} 超时")
            return False
        except Exception as e:
            logger.error(f"停止虚拟机 {vm_name} 时出错: {e}")
            return False

    def restart_vm(self, vm_name: str) -> bool:
        """
        强制重启虚拟机（简化版本，移除服务检测）
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            是否成功重启
        """
        
        try:
            console_logger.info(f"正在强制重启虚拟机: {vm_name}")
            
            # 首先强制停止虚拟机
            logger.debug(f"强制停止虚拟机: {vm_name}")
            stop_result = subprocess.run(
                [self.vboxmanage_path, 'controlvm', vm_name, 'poweroff'],
                capture_output=True, timeout=30
            )
            
            if stop_result.returncode != 0:
                logger.warning(f"强制停止虚拟机 {vm_name} 失败，但继续重启流程")
            
            # 等待一段时间确保虚拟机完全停止
            import time
            time.sleep(3)
            
            # 然后启动虚拟机
            logger.debug(f"启动虚拟机: {vm_name}")
            start_result = subprocess.run(
                [self.vboxmanage_path, 'startvm', vm_name, '--type', VBOX_START_TYPE],
                capture_output=True, timeout=60  # 减少超时时间
            )
            
            # 简化编码处理
            try:
                stderr = start_result.stderr.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                stderr = start_result.stderr.decode('gbk', errors='ignore')
            
            if start_result.returncode == 0:
                logger.info(f"虚拟机 {vm_name} 强制重启成功")
                return True
            else:
                logger.error(f"虚拟机 {vm_name} 强制重启失败: {stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"强制重启虚拟机 {vm_name} 超时")
            return False
        except Exception as e:
            logger.error(f"强制重启虚拟机 {vm_name} 时出错: {e}")
            return False


    
    def get_all_vm_status(self, scan_status: bool = False, quiet: bool = False) -> List[Dict]:
        """
        获取所有虚拟机状态（修复版本，正确获取虚拟机状态）
        
        Args:
            scan_status: 是否扫描虚拟机状态，默认False以避免超时
            quiet: 是否静默模式，不输出"发现已停止虚拟机"日志
            
        Returns:
            虚拟机状态列表
        """
        # 快速扫描虚拟机文件
        vms = self.scan_vms(scan_status=False)
        vm_status_list = []
        start_failures = self.get_start_failures()
        
        for vm in vms:
            # 获取虚拟机真实状态
            try:
                real_status = self.get_vm_status(vm['name'])
                # 减少调试输出，避免重复
                # logger.debug(f"获取虚拟机 {vm['name']} 真实状态: {real_status}")
            except Exception as e:
                logger.warning(f"获取虚拟机 {vm['name']} 状态失败: {e}")
                real_status = 'unknown'
            
            vm_info = {
                'name': vm['name'],
                'uuid': vm['uuid'],
                'path': vm['path'],
                'status': real_status,  # 使用真实状态
                'last_check': vm['last_check'],
                'start_count': self.get_vm_start_count(vm['name']),  # 添加启动次数
                'delete_threshold': self.max_start_count  # 添加删除阈值
            }
            
            # 检查虚拟机是否已被删除
            if self.is_vm_deleted(vm['name']):
                vm_info['deleted'] = True
                vm_info['status'] = 'deleted'  # 覆盖状态为已删除
                # 添加备份路径信息
                backup_dir = os.path.join(os.path.dirname(self.vbox_dir), self.delete_backup_dir)
                vm_info['backup_path'] = backup_dir
            
            # 添加启动失败信息
            if vm['name'] in start_failures:
                vm_info['start_failure'] = True
                vm_info['failure_count'] = start_failures[vm['name']]['count']
                vm_info['failure_timestamp'] = start_failures[vm['name']]['last_failure']
            
            # 添加异常状态信息
            exception_status = self.get_vm_exception_status(vm['name'])
            if exception_status:
                vm_info['exception'] = True
                vm_info['exception_operation'] = exception_status['operation']
                vm_info['exception_message'] = exception_status['error_message']
                vm_info['exception_timestamp'] = exception_status['timestamp']
                vm_info['exception_count'] = exception_status['count']
            
            vm_status_list.append(vm_info)
            
            # 更新内部状态
            self.vms[vm['name']] = vm_info
        
        return vm_status_list
    
    def _detect_status_changes(self, current_vm_status: List[Dict]) -> bool:
        """
        检测虚拟机状态变化
        
        Args:
            current_vm_status: 当前虚拟机状态列表
            
        Returns:
            bool: 是否有状态变化
        """
        if not self.last_vm_status:
            # 第一次运行，记录状态但不报告变化
            self.last_vm_status = {vm['name']: vm['status'] for vm in current_vm_status}
            return False
        
        # 创建当前状态字典
        current_status = {vm['name']: vm['status'] for vm in current_vm_status}
        
        # 检测变化
        changes_detected = False
        
        # 检查新增的虚拟机
        for vm_name, status in current_status.items():
            if vm_name not in self.last_vm_status:
                monitor_logger.info(f"检测到新增虚拟机: {vm_name} (状态: {status})")
                changes_detected = True
        
        # 检查状态变化的虚拟机
        for vm_name, status in current_status.items():
            if vm_name in self.last_vm_status:
                last_status = self.last_vm_status[vm_name]
                if status != last_status:
                    monitor_logger.info(f"检测到虚拟机状态变化: {vm_name} {last_status} -> {status}")
                    changes_detected = True
        
        # 检查删除的虚拟机
        for vm_name in self.last_vm_status:
            if vm_name not in current_status:
                monitor_logger.info(f"检测到虚拟机删除: {vm_name}")
                changes_detected = True
        
        # 更新上次状态
        self.last_vm_status = current_status.copy()
        
        return changes_detected
    
    def auto_start_stopped_vms(self) -> List[Dict]:
        """
        自动启动已停止的虚拟机
        
        Returns:
            启动结果列表
        """
        results = []
        vm_status_list = self.get_all_vm_status(quiet=True)  # 静默模式，避免重复日志
        
        monitor_logger.info(f"开始自动启动检查，共发现 {len(vm_status_list)} 个虚拟机")
        monitor_logger.info(f"当前监控实例auto_start_enabled状态: {self.auto_start_enabled}")
        monitor_logger.info(f"虚拟机状态列表: {[(vm['name'], vm['status']) for vm in vm_status_list]}")
        
        # 强制重新加载配置文件以确保获取最新的AUTO_START_STOPPED_NUM
        try:
            import importlib
            import sys
            if 'config' in sys.modules:
                importlib.reload(sys.modules['config'])
                monitor_logger.info("已重新加载config模块以确保获取最新配置")
        except Exception as e:
            monitor_logger.warning(f"重新加载config模块失败: {e}")
        
        # 获取配置的启动数量
        try:
            from config import AUTO_START_STOPPED_NUM
            max_start_num = AUTO_START_STOPPED_NUM
            monitor_logger.info(f"成功从配置文件读取AUTO_START_STOPPED_NUM: {max_start_num}")
        except ImportError:
            max_start_num = 4  # 默认值
            logger.warning("无法导入AUTO_START_STOPPED_NUM配置，使用默认值4")
            monitor_logger.warning("无法导入AUTO_START_STOPPED_NUM配置，使用默认值4")
        
        monitor_logger.info(f"配置的自动启动数量: {max_start_num}")
        logger.info(f"自动启动数量限制: {max_start_num}")
        
        # 统计当前运行中的虚拟机数量
        running_vms = [vm for vm in vm_status_list if vm['status'] == 'running']
        running_count = len(running_vms)
        monitor_logger.info(f"当前运行中的虚拟机数量: {running_count}")
        logger.info(f"当前运行中的虚拟机数量: {running_count}")
        
        # 检查是否需要停止多余的虚拟机
        if running_count > max_start_num:
            excess_count = running_count - max_start_num
            monitor_logger.info(f"当前运行中的虚拟机数量({running_count})超过设定数量({max_start_num})，需要停止 {excess_count} 个虚拟机")
            console_logger.info(f"当前运行中的虚拟机数量({running_count})超过设定数量({max_start_num})，需要停止 {excess_count} 个虚拟机")
            
            # 停止多余的虚拟机
            stopped_count = 0
            for vm in running_vms:
                if stopped_count >= excess_count:
                    break
                
                # 检查是否为母盘虚拟机例外
                if ENABLE_MASTER_VM_EXCEPTIONS:
                    try:
                        from config import MASTER_VM_EXCEPTIONS
                        if vm['name'] in MASTER_VM_EXCEPTIONS:
                            logger.info(f"虚拟机 {vm['name']} 在母盘虚拟机例外列表中，跳过停止操作")
                            monitor_logger.info(f"虚拟机 {vm['name']} 在母盘虚拟机例外列表中，跳过停止操作")
                            continue
                    except ImportError:
                        logger.warning("无法导入MASTER_VM_EXCEPTIONS配置，跳过母盘虚拟机检查")
                        monitor_logger.warning("无法导入MASTER_VM_EXCEPTIONS配置，跳过母盘虚拟机检查")
                
                console_logger.info(f"准备停止第 {stopped_count + 1} 个虚拟机: {vm['name']}")
                monitor_logger.info(f"准备停止第 {stopped_count + 1} 个虚拟机: {vm['name']}")
                
                success = self.stop_vm(vm['name'])
                result = {
                    'name': vm['name'],
                    'original_status': vm['status'],
                    'action': 'stop',
                    'success': success,
                    'timestamp': datetime.now().isoformat()
                }
                results.append(result)
                stopped_count += 1
                
                if success:
                    console_logger.info(f"自动停止虚拟机 {vm['name']} 成功 (第{stopped_count}个)")
                    monitor_logger.info(f"自动停止虚拟机 {vm['name']} 成功 (第{stopped_count}个)")
                else:
                    console_logger.error(f"自动停止虚拟机 {vm['name']} 失败")
                    monitor_logger.error(f"自动停止虚拟机 {vm['name']} 失败")
            
            monitor_logger.info(f"停止操作完成，共停止 {stopped_count} 个虚拟机")
            console_logger.info(f"停止操作完成，共停止 {stopped_count} 个虚拟机")
            return results
        
        # 检查是否已达到目标运行数量
        if running_count >= max_start_num:
            monitor_logger.debug(f"当前运行中的虚拟机数量({running_count})已达到或超过设定数量({max_start_num})，无需启动新虚拟机")
            # console_logger.info(f"当前运行中的虚拟机数量({running_count})已达到或超过设定数量({max_start_num})，无需启动新虚拟机")
            # 返回空结果，表示无需操作
            return results
        
        # 计算还可以启动的虚拟机数量
        remaining_slots = max_start_num - running_count
        monitor_logger.debug(f"还可以启动的虚拟机数量: {remaining_slots}")
        # console_logger.info(f"还可以启动的虚拟机数量: {remaining_slots}")
        
        # 检查是否有可启动的虚拟机
        stopped_vms = [vm for vm in vm_status_list if vm['status'] in ['poweroff', 'aborted']]
        if not stopped_vms:
            monitor_logger.debug("没有发现可启动的虚拟机")
            # console_logger.info("没有发现可启动的虚拟机")
            return results
        
        # 检查是否启用随机选择
        try:
            from config import ENABLE_RANDOM_VM_SELECTION
            enable_random = ENABLE_RANDOM_VM_SELECTION
        except ImportError:
            enable_random = True  # 默认启用随机选择
            monitor_logger.warning("无法导入ENABLE_RANDOM_VM_SELECTION配置，使用默认值True")
        
        # 如果启用随机选择，对虚拟机列表进行智能随机排序
        if enable_random and len(stopped_vms) > 1:
            import random
            
            # 获取每个虚拟机的启动次数
            vm_start_counts = {}
            for vm in stopped_vms:
                vm_start_counts[vm['name']] = self.get_vm_start_count(vm['name'])
            
            # 按启动次数排序，启动次数少的优先
            stopped_vms.sort(key=lambda x: vm_start_counts.get(x['name'], 0))
            
            # 对启动次数相同的虚拟机进行随机排序
            current_count = None
            start_idx = 0
            
            for i, vm in enumerate(stopped_vms):
                vm_count = vm_start_counts.get(vm['name'], 0)
                
                if current_count is None:
                    current_count = vm_count
                elif vm_count != current_count:
                    # 对启动次数相同的虚拟机进行随机排序
                    if i - start_idx > 1:
                        random.shuffle(stopped_vms[start_idx:i])
                    current_count = vm_count
                    start_idx = i
            
            # 处理最后一组
            if len(stopped_vms) - start_idx > 1:
                random.shuffle(stopped_vms[start_idx:])
            
            monitor_logger.info(f"启用智能随机选择，已对 {len(stopped_vms)} 个虚拟机进行排序")
            console_logger.info(f"启用智能随机选择，已对 {len(stopped_vms)} 个虚拟机进行排序")
            
            # 记录启动次数信息
            for vm in stopped_vms[:min(3, len(stopped_vms))]:  # 只显示前3个
                count = vm_start_counts.get(vm['name'], 0)
                monitor_logger.info(f"虚拟机 {vm['name']} 启动次数: {count}")
        else:
            monitor_logger.info(f"使用顺序选择，将按扫描顺序启动虚拟机")
            console_logger.info(f"使用顺序选择，将按扫描顺序启动虚拟机")
        
        started_count = 0
        failed_vms = []  # 记录启动失败的虚拟机
        
        for vm in stopped_vms:
            # 检查是否启用自动启动功能
            # 使用监控实例中的auto_start_enabled状态，而不是配置文件
            if not self.auto_start_enabled:
                console_logger.info(f"自动启动功能已禁用，跳过虚拟机: {vm['name']}")
                monitor_logger.info(f"自动启动功能已禁用，跳过虚拟机: {vm['name']}")
                monitor_logger.info(f"当前监控实例auto_start_enabled状态: {self.auto_start_enabled}")
                continue
            
            # 检查是否已达到可启动数量限制
            if started_count >= remaining_slots:
                console_logger.info(f"已达到可启动数量限制 {remaining_slots}，跳过剩余虚拟机")
                monitor_logger.info(f"已达到可启动数量限制 {remaining_slots}，跳过剩余虚拟机")
                monitor_logger.info(f"已启动数量: {started_count}, 可启动数量: {remaining_slots}")
                break
            
            # 检查是否为母盘虚拟机例外
            if ENABLE_MASTER_VM_EXCEPTIONS:
                try:
                    from config import MASTER_VM_EXCEPTIONS
                    if vm['name'] in MASTER_VM_EXCEPTIONS:
                        logger.info(f"虚拟机 {vm['name']} 在母盘虚拟机例外列表中，跳过自动启动")
                        monitor_logger.info(f"虚拟机 {vm['name']} 在母盘虚拟机例外列表中，跳过自动启动")
                        continue
                except ImportError:
                    logger.warning("无法导入MASTER_VM_EXCEPTIONS配置，跳过母盘虚拟机检查")
                    monitor_logger.warning("无法导入MASTER_VM_EXCEPTIONS配置，跳过母盘虚拟机检查")
            
            # 尝试启动虚拟机，使用配置文件中的重试设置
            vm_started = False
            retry_count = 0
            
            # 从配置文件获取重试设置
            try:
                from config import VM_START_MAX_RETRIES, VM_START_RETRY_INTERVAL
                max_retries = VM_START_MAX_RETRIES
                retry_interval = VM_START_RETRY_INTERVAL
            except ImportError:
                # 如果无法获取配置，使用默认值
                max_retries = 3
                retry_interval = 5
                monitor_logger.warning("无法获取虚拟机重试配置，使用默认值")
            
            while retry_count <= max_retries and not vm_started:
                if retry_count > 0:
                    console_logger.info(f"第 {retry_count} 次重试启动虚拟机: {vm['name']}")
                    monitor_logger.info(f"第 {retry_count} 次重试启动虚拟机: {vm['name']}")
                    console_logger.info(f"等待 {retry_interval} 秒后进行重试...")
                    monitor_logger.info(f"等待 {retry_interval} 秒后进行重试...")
                    time.sleep(retry_interval)  # 使用配置文件中的重试间隔时间
                else:
                    console_logger.info(f"准备启动第 {started_count + 1} 个虚拟机: {vm['name']}")
                    monitor_logger.debug(f"尝试启动虚拟机: {vm['name']}")
                
                success = self.start_vm(vm['name'])
                
                if success:
                    vm_started = True
                    # 记录虚拟机启动次数
                    self.increment_vm_start_count(vm['name'])
                    console_logger.info(f"自动启动虚拟机 {vm['name']} 成功 (第{started_count + 1}个)")
                    monitor_logger.info(f"自动启动虚拟机 {vm['name']} 成功 (第{started_count + 1}个)")
                else:
                    retry_count += 1
                    if retry_count <= max_retries:
                        console_logger.warning(f"启动虚拟机 {vm['name']} 失败，将进行第 {retry_count} 次重试")
                        monitor_logger.warning(f"启动虚拟机 {vm['name']} 失败，将进行第 {retry_count} 次重试")
                    else:
                        console_logger.error(f"启动虚拟机 {vm['name']} 失败，已重试 {max_retries} 次，跳过该虚拟机")
                        monitor_logger.error(f"启动虚拟机 {vm['name']} 失败，已重试 {max_retries} 次，跳过该虚拟机")
                        # 记录启动失败，供前端显示
                        self.mark_start_failure(vm['name'])
                        failed_vms.append(vm['name'])
            
            # 记录结果
            result = {
                'name': vm['name'],
                'original_status': vm['status'],
                'action': 'start',
                'success': vm_started,
                'retry_count': retry_count,
                'timestamp': datetime.now().isoformat()
            }
            results.append(result)
            
            if vm_started:
                started_count += 1
        
        monitor_logger.info(f"自动启动检查完成，共处理 {len(results)} 个虚拟机，启动数量限制: {max_start_num}, 当前运行中: {running_count}, 已启动: {started_count}")
        console_logger.info(f"自动启动检查完成，共处理 {len(results)} 个虚拟机，启动数量限制: {max_start_num}, 当前运行中: {running_count}, 已启动: {started_count}")
        
        # 如果有启动失败的虚拟机，输出详细信息
        if failed_vms:
            console_logger.warning(f"发现 {len(failed_vms)} 个虚拟机启动失败: {', '.join(failed_vms)}")
            monitor_logger.warning(f"发现 {len(failed_vms)} 个虚拟机启动失败: {', '.join(failed_vms)}")
        
        return results
    
    def start_monitoring(self, interval: int = None, auto_start: bool = True, start_time: str = None):
        # 如果没有指定间隔，从配置文件获取默认值
        if interval is None:
            from config import AUTO_MONITOR_INTERVAL_VALUE
            interval = AUTO_MONITOR_INTERVAL_VALUE
        """
        开始监控虚拟机
        
        Args:
            interval: 监控间隔（秒）
            auto_start: 是否自动启动未运行的虚拟机
            start_time: 监控启动时间戳
        """
        if self.monitoring:
            console_logger.info("监控配置已更新，重新启动监控以应用新设置")
            monitor_logger.info("监控配置已更新，重新启动监控以应用新设置")
            # 静默停止监控，不输出停止日志
            self._silent_stop_monitoring()
            # 等待一小段时间确保监控线程完全停止
            time.sleep(2)  # 增加等待时间
            
            # 确保监控状态已重置
            if self.monitoring:
                monitor_logger.warning("监控状态未正确重置，强制重置")
                self.monitoring = False
        
        self.monitoring = True
        self.auto_start_enabled = auto_start
        self.last_monitor_results = []
        self.monitor_start_time = start_time or datetime.now().isoformat()
        
        # 格式化启动时间显示
        try:
            # 使用当前时间作为启动时间，避免时区问题
            formatted_start_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        except:
            formatted_start_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        
        # 后台日志控制台打印监控启动信息
        auto_start_text = "自动启动模式" if auto_start else "仅监控模式"
        # 移除重复的启动信息输出，避免重复打印
        # console_logger.info(f"监控已启动，间隔{interval}秒，{auto_start_text}，启动时间: {formatted_start_time}")
        
        # 保留一条主要的启动信息
        logger.info(f"自动监控已启动，间隔: {interval}秒，自动启动: {auto_start}")
        monitor_logger.info(f"自动监控已启动，间隔: {interval}秒，自动启动: {auto_start}")
        # 移除重复的启动时间信息
        # monitor_logger.info(f"自动监控启动时间: {self.monitor_start_time}")
        # monitor_logger.info(f"监控配置详情: 间隔={interval}秒, 自动启动={auto_start}, 启动时间={self.monitor_start_time}")
        
        def monitor_task():
            # 记录监控任务启动信息
            monitor_logger.debug(f"监控任务启动，间隔: {interval}秒，自动启动: {auto_start}")
            
            # 计算第一次执行的时间
            if start_time:
                try:
                    start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    now = datetime.now(start_datetime.tzinfo)
                    time_diff = (start_datetime - now).total_seconds()
                    
                    if time_diff > 0:
                        monitor_logger.info(f"等待 {time_diff} 秒后开始第一次监控检查...")
                        time.sleep(time_diff)
                except Exception as e:
                    monitor_logger.warning(f"时间计算错误，立即开始监控: {e}")
            
            monitor_logger.debug(f"开始监控循环，间隔: {interval}秒")
            
            # 保存初始间隔值，使用动态获取的最新值
            try:
                from config import AUTO_MONITOR_INTERVAL_VALUE
                current_interval = AUTO_MONITOR_INTERVAL_VALUE
            except ImportError:
                current_interval = interval
                monitor_logger.warning("无法获取AUTO_MONITOR_INTERVAL_VALUE配置，使用传入的间隔值")
            
            # 立即执行第一次检查
            monitor_logger.debug("立即执行第一次监控检查...")
            
            # 记录监控循环开始时间
            loop_start_time = time.time()
            monitor_logger.debug(f"监控循环开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 计算下次执行时间，确保严格按照间隔执行
            next_execution_time = datetime.now()
            
            while self.monitoring:
                try:
                    # 计算当前时间与下次执行时间的差值
                    current_time = datetime.now()
                    time_until_next = (next_execution_time - current_time).total_seconds()
                    
                    # 如果距离下次执行还有时间，则等待
                    if time_until_next > 0:
                        monitor_logger.debug(f"等待 {time_until_next:.2f} 秒后执行下次检查")
                        time.sleep(time_until_next)
                    
                    # 记录本次执行开始时间
                    execution_start_time = time.time()
                    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    monitor_logger.debug(f"开始执行监控检查 - {current_time_str}")
                    
                    # 动态获取最新的配置
                    try:
                        import importlib
                        import sys
                        if 'config' in sys.modules:
                            importlib.reload(sys.modules['config'])
                        from config import AUTO_MONITOR_INTERVAL_VALUE
                        new_interval = AUTO_MONITOR_INTERVAL_VALUE
                        
                        # 检查间隔是否发生变化
                        if new_interval != current_interval:
                            monitor_logger.info(f"检测到监控间隔变化: {current_interval}秒 -> {new_interval}秒")
                            current_interval = new_interval
                        else:
                            monitor_logger.debug(f"监控间隔无变化: {current_interval}秒")
                    except Exception as e:
                        monitor_logger.warning(f"重新加载配置失败，使用当前间隔: {e}")
                        # 如果重载失败，继续使用当前间隔
                        # current_interval 已经在循环开始时设置为 interval
                    
                    logger.debug("执行自动监控检查...")
                    monitor_logger.debug("执行自动监控检查...")
                    monitor_logger.debug(f"自动监控状态: 正在执行，间隔: {interval}秒，当前间隔: {current_interval}秒")
                    
                    # 移除VirtualBox服务检测，直接执行监控任务
                    
                            # 精简调试信息，只保留必要信息
                    
                    # 获取所有虚拟机状态（非静默模式，用于监控任务）
                    vm_status_list = self.get_all_vm_status(quiet=False)
                    # 用于自动启动检查的已停止虚拟机（包括poweroff和aborted）
                    stopped_vms_for_auto_start = [vm for vm in vm_status_list if vm['status'] in ['poweroff', 'aborted']]
                    
                    # 精简虚拟机状态输出
                    
                    # 统计虚拟机状态
                    running_vms = [vm for vm in vm_status_list if vm['status'] == 'running']
                    paused_vms = [vm for vm in vm_status_list if vm['status'] == 'paused']
                    stopped_vms = [vm for vm in vm_status_list if vm['status'] in ['poweroff', 'aborted']]  # 包括aborted状态
                    error_vms = [vm for vm in vm_status_list if vm['status'] in ['error', 'unknown']]  # 排除aborted，因为它已计入stopped_vms
                    
                    # 检测状态变化
                    status_changed = self._detect_status_changes(vm_status_list)
                    
                    # 记录状态监控结果
                    status_result = {
                        'timestamp': datetime.now().isoformat(),
                        'total_vms': len(vm_status_list),
                        'running_vms': len(running_vms),
                        'stopped_vms': len(stopped_vms),
                        'paused_vms': len(paused_vms),
                        'error_vms': len(error_vms),
                        'auto_start_enabled': self.auto_start_enabled
                    }
                    
                    # 只在状态发生变化时输出详细日志
                    if status_changed:
                        # 精简状态统计输出
                        status_summary = f"虚拟机状态：运行中 {len(running_vms)}台，已关闭 {len(stopped_vms)}台，暂停 {len(paused_vms)}台，异常 {len(error_vms)}台"
                        console_logger.info(status_summary)
                        
                        # 确保"发现已停止的虚拟机"的数量与状态统计一致
                        if stopped_vms_for_auto_start:
                            console_logger.info(f"发现 {len(stopped_vms)} 个已停止的虚拟机")
                    else:
                        # 状态未变化时，只记录调试信息
                        monitor_logger.debug(f"虚拟机状态无变化: 运行中 {len(running_vms)}台，已关闭 {len(stopped_vms)}台，暂停 {len(paused_vms)}台，异常 {len(error_vms)}台")
                    
                    # 检查是否有已停止的虚拟机（只在监控任务中输出）
                    if stopped_vms_for_auto_start:
                        # 检查自动启动是否启用
                        if self.auto_start_enabled:
                            # 只在状态变化时输出自动启动日志
                            if status_changed:
                                console_logger.info("自动启动功能已启用，开始启动已停止的虚拟机...")
                            
                            # 调用自动启动方法
                            results = self.auto_start_stopped_vms()
                            
                            # 保存执行结果
                            self.last_monitor_results = results
                            
                            if results:
                                start_count = sum(1 for r in results if r['action'] == 'start' and r['success'])
                                stop_count = sum(1 for r in results if r['action'] == 'stop' and r['success'])
                                failed_count = sum(1 for r in results if not r['success'])
                                total_operations = len(results)
                                
                                # 只在有操作结果且状态变化时输出日志
                                if status_changed and (stop_count > 0 or start_count > 0 or failed_count > 0):
                                    if stop_count > 0:
                                        console_logger.info(f"停止 {stop_count} 个虚拟机")
                                        monitor_logger.info(f"本次检查执行了 {total_operations} 个操作，成功停止 {stop_count} 个虚拟机")
                                    elif start_count > 0:
                                        if failed_count > 0:
                                            console_logger.info(f"启动 {start_count} 个虚拟机，{failed_count} 个操作失败")
                                            monitor_logger.info(f"本次检查启动了 {start_count} 个虚拟机，{failed_count} 个操作失败")
                                        else:
                                            console_logger.info(f"启动 {start_count} 个虚拟机")
                                            monitor_logger.info(f"本次检查启动了 {start_count} 个虚拟机")
                                    else:
                                        if failed_count > 0:
                                            console_logger.warning(f"{failed_count} 个操作失败")
                                            monitor_logger.warning(f"本次检查执行了 {total_operations} 个操作，但全部失败")
                                
                                # 记录详细的启动结果（只在状态变化时）
                                if status_changed:
                                    for result in results:
                                        if result['action'] == 'start':
                                            if result['success']:
                                                monitor_logger.info(f"虚拟机 {result['name']} 启动成功")
                                            else:
                                                logger.warning(f"虚拟机 {result['name']} 启动失败")
                                                monitor_logger.warning(f"虚拟机 {result['name']} 启动失败")
                                        elif result['action'] == 'stop':
                                            if result['success']:
                                                monitor_logger.info(f"虚拟机 {result['name']} 停止成功")
                                            else:
                                                logger.warning(f"虚拟机 {result['name']} 停止失败")
                                                monitor_logger.warning(f"虚拟机 {result['name']} 停止失败")
                            else:
                                # 检查是否有启动失败的情况
                                failed_vms = [vm for vm in stopped_vms_for_auto_start if vm.get('start_failure', False)]
                                if failed_vms and status_changed:
                                    console_logger.warning(f"发现 {len(failed_vms)} 个虚拟机启动失败")
                                    monitor_logger.warning(f"发现 {len(failed_vms)} 个虚拟机启动失败: {[vm['name'] for vm in failed_vms]}")
                                else:
                                    # 使用详细的状态统计日志，不再显示简单的消息
                                    self.last_monitor_results = []
                        else:
                            # 只在状态变化时输出禁用日志
                            if status_changed:
                                console_logger.info(f"发现 {len(stopped_vms_for_auto_start)} 个已停止的虚拟机，但自动启动已禁用")
                                monitor_logger.info(f"发现 {len(stopped_vms_for_auto_start)} 个已停止的虚拟机，但自动启动已禁用")
                                monitor_logger.info(f"仅执行状态监控，不进行自动启动操作")
                                monitor_logger.info(f"当前监控实例auto_start_enabled状态: {self.auto_start_enabled}")
                            self.last_monitor_results = []
                    else:
                        # 使用详细的状态统计日志，不再显示简单的消息
                        self.last_monitor_results = []
                    
                    # 检查自动删除
                    if self.auto_delete_enabled:
                        console_logger.info("🔍 检查自动删除条件...")
                        monitor_logger.info("🔍 检查自动删除条件...")
                        
                        deleted_vms = []
                        for vm in vm_status_list:
                            vm_name = vm['name']
                            current_count = self.vm_start_counts.get(vm_name, 0)
                            
                            if current_count >= self.max_start_count:
                                # 检查是否已被删除
                                if not self.is_vm_deleted(vm_name):
                                    console_logger.warning(f"🚨 检测到虚拟机 {vm_name} 启动次数 {current_count} 已达到删除阈值 {self.max_start_count}")
                                    monitor_logger.warning(f"🚨 检测到虚拟机 {vm_name} 启动次数 {current_count} 已达到删除阈值 {self.max_start_count}")
                                    console_logger.info(f"🔄 准备启动自动删除任务...")
                                    monitor_logger.info(f"🔄 准备启动自动删除任务...")
                                    
                                    # 异步执行删除操作
                                    import threading
                                    delete_thread = threading.Thread(target=self.auto_delete_vm, args=(vm_name,))
                                    delete_thread.daemon = True
                                    delete_thread.start()
                                    
                                    deleted_vms.append(vm_name)
                                    console_logger.info(f"✅ 虚拟机 {vm_name} 自动删除任务已启动")
                                    monitor_logger.info(f"✅ 虚拟机 {vm_name} 自动删除任务已启动")
                                else:
                                    monitor_logger.debug(f"ℹ️ 虚拟机 {vm_name} 已被标记为删除")
                        
                        if deleted_vms:
                            console_logger.info(f"📊 本次检查启动了 {len(deleted_vms)} 个自动删除任务")
                            monitor_logger.info(f"📊 本次检查启动了 {len(deleted_vms)} 个自动删除任务")
                        else:
                            monitor_logger.debug("📊 本次检查没有需要删除的虚拟机")
                    else:
                        monitor_logger.debug("📊 自动删除功能未启用，跳过检查")
                    
                except Exception as e:
                    console_logger.error(f"监控任务出错: {e}")
                    monitor_logger.error(f"监控任务出错: {e}")
                    self.last_monitor_results = []
                
                # 计算本次执行耗时
                execution_time = time.time() - execution_start_time
                monitor_logger.debug(f"本次监控执行耗时: {execution_time:.2f}秒")
                
                # 统计本次执行结果
                total_vms_checked = len(vm_status_list)
                running_vms_count = len(running_vms)
                stopped_vms_count = len(stopped_vms)
                paused_vms_count = len(paused_vms)
                error_vms_count = len(error_vms)
                
                # 统计启动的虚拟机数量
                started_vms_count = 0
                failed_start_count = 0
                if self.last_monitor_results:
                    started_vms_count = sum(1 for r in self.last_monitor_results if r['action'] == 'start' and r['success'])
                    failed_start_count = sum(1 for r in self.last_monitor_results if r['action'] == 'start' and not r['success'])
                
                # 打印详细的执行结果
                execution_summary = f"本次监控任务执行结果 - 检查虚拟机: {total_vms_checked}台 (运行中: {running_vms_count}台, 已关闭: {stopped_vms_count}台, 暂停: {paused_vms_count}台, 异常: {error_vms_count}台)"
                execution_summary += f", 启动虚拟机: {started_vms_count}台"
                if failed_start_count > 0:
                    execution_summary += f", 启动失败: {failed_start_count}台"
                
                console_logger.info(execution_summary)
                monitor_logger.info(execution_summary)
                
                # 动态获取最新的间隔值
                try:
                    from config import AUTO_MONITOR_INTERVAL_VALUE
                    new_interval = AUTO_MONITOR_INTERVAL_VALUE
                    
                    # 检查间隔是否发生变化
                    if new_interval != current_interval:
                        monitor_logger.info(f"检测到监控间隔变化: {current_interval}秒 -> {new_interval}秒")
                        current_interval = new_interval
                except ImportError:
                    # 如果无法获取配置，使用保存的间隔值
                    monitor_logger.warning("无法获取AUTO_MONITOR_INTERVAL_VALUE配置，使用默认值300秒")
                    current_interval = 300
                
                # 计算下次执行时间，确保严格按照间隔执行
                # 使用动态获取的最新间隔值，确保配置变化时能及时生效
                next_execution_time = next_execution_time + timedelta(seconds=current_interval)
                
                # 计算本次执行耗时
                execution_time = time.time() - execution_start_time
                monitor_logger.debug(f"本次执行耗时: {execution_time:.2f}秒，设定间隔: {current_interval}秒")
                
                # 显示下次执行时间
                next_execution_msg = f"下次监控任务执行时间: {next_execution_time.strftime('%Y-%m-%d %H:%M:%S')}"
                console_logger.info(next_execution_msg)
                monitor_logger.info(next_execution_msg)
                
                # 添加调试信息
                monitor_logger.debug(f"监控循环完成，下次执行时间: {next_execution_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 记录本次循环完成时间
                loop_completion_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                monitor_logger.debug(f"本次监控检查完成 - {loop_completion_time}")
        
        self.monitor_thread = threading.Thread(target=monitor_task, daemon=MONITOR_THREAD_DAEMON)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        console_logger.info("自动监控已停止")
        monitor_logger.info("自动监控已停止")
        monitor_logger.info("自动监控状态: 已关闭")
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            # 从配置文件获取超时时间
            from config import VM_STATUS_TIMEOUT
            thread_timeout = min(VM_STATUS_TIMEOUT, 10)  # 线程停止使用较短超时
            monitor_logger.info(f"等待监控线程停止，超时时间: {thread_timeout}秒")
            self.monitor_thread.join(timeout=thread_timeout)
            
            if self.monitor_thread.is_alive():
                monitor_logger.warning("监控线程未在超时时间内停止，强制终止")
                # 在Python中无法强制终止线程，但可以设置标志
                self.monitoring = False
            else:
                monitor_logger.info("监控线程已成功停止")
        
        # 重置监控线程引用
        self.monitor_thread = None
    
    def _silent_stop_monitoring(self):
        """静默停止监控（不输出停止日志）"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        # 不输出停止日志，只记录到监控日志
        monitor_logger.info("自动监控已停止（静默模式）")
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            # 从配置文件获取超时时间
            from config import VM_STATUS_TIMEOUT
            thread_timeout = min(VM_STATUS_TIMEOUT, 10)  # 线程停止使用较短超时
            monitor_logger.info(f"等待监控线程停止，超时时间: {thread_timeout}秒")
            self.monitor_thread.join(timeout=thread_timeout)
            
            if self.monitor_thread.is_alive():
                monitor_logger.warning("监控线程未在超时时间内停止，强制终止")
                # 在Python中无法强制终止线程，但可以设置标志
                self.monitoring = False
            else:
                monitor_logger.info("监控线程已成功停止")
        
        # 重置监控线程引用
        self.monitor_thread = None
    
    def get_vm_info(self, vm_name: str) -> Optional[Dict]:
        """
        获取虚拟机详细信息（简化版本，避免超时）
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            虚拟机详细信息
        """
        try:
            # 从配置文件获取超时时间
            from config import VM_INFO_TIMEOUT
            info_timeout = VM_INFO_TIMEOUT
            
            logger.debug(f"获取虚拟机 {vm_name} 详细信息 (超时: {info_timeout}秒)")
            result = subprocess.run(
                [self.vboxmanage_path, 'showvminfo', vm_name],
                capture_output=True, timeout=info_timeout
            )
            
            if result.returncode == 0:
                try:
                    stdout = result.stdout.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    stdout = result.stdout.decode('gbk', errors='ignore')
                
                info = {}
                lines = stdout.strip().split('\n')
                
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip()] = value.strip()
                
                return info
            else:
                logger.warning(f"获取虚拟机 {vm_name} 详细信息失败，返回码: {result.returncode}")
                return None
            
        except subprocess.TimeoutExpired:
            logger.warning(f"获取虚拟机 {vm_name} 详细信息超时")
            return None
        except Exception as e:
            logger.warning(f"获取虚拟机 {vm_name} 详细信息时出错: {e}")
            return None

    def monitor_vm_status(self) -> Dict:
        """
        监控虚拟机状态
        
        Returns:
            监控结果字典
        """
        try:
            logger.debug("开始监控虚拟机状态")
            
            # 获取所有虚拟机状态（静默模式）
            vm_status_list = self.get_all_vm_status(quiet=True)
            
            # 统计信息
            total_vms = len(vm_status_list)
            running_vms = len([vm for vm in vm_status_list if vm['status'] == 'running'])
            stopped_vms = len([vm for vm in vm_status_list if vm['status'] in ['poweroff', 'aborted']])
            paused_vms = len([vm for vm in vm_status_list if vm['status'] == 'paused'])
            
            # 检查状态变化和自动删除
            status_changes = []
            deleted_vms = []
            current_time = datetime.now()
            
            for vm in vm_status_list:
                # 检查自动删除
                if self.auto_delete_enabled:
                    vm_name = vm['name']
                    current_count = self.vm_start_counts.get(vm_name, 0)
                    
                    if current_count >= self.max_start_count:
                        # 检查是否已被删除
                        if not self.is_vm_deleted(vm_name):
                            logger.warning(f"🚨 检测到虚拟机 {vm_name} 启动次数 {current_count} 已达到删除阈值 {self.max_start_count}")
                            monitor_logger.warning(f"🚨 检测到虚拟机 {vm_name} 启动次数 {current_count} 已达到删除阈值 {self.max_start_count}")
                            logger.info(f"🔄 准备启动自动删除任务...")
                            monitor_logger.info(f"🔄 准备启动自动删除任务...")
                            
                            # 异步执行删除操作
                            import threading
                            delete_thread = threading.Thread(target=self.auto_delete_vm, args=(vm_name,))
                            delete_thread.daemon = True
                            delete_thread.start()
                            
                            deleted_vms.append(vm_name)
                            logger.info(f"✅ 虚拟机 {vm_name} 自动删除任务已启动")
                            monitor_logger.info(f"✅ 虚拟机 {vm_name} 自动删除任务已启动")
                        else:
                            logger.debug(f"ℹ️ 虚拟机 {vm_name} 已被标记为删除")
                            monitor_logger.debug(f"ℹ️ 虚拟机 {vm_name} 已被标记为删除")
                
                # 这里可以添加状态变化检测逻辑
                # 暂时返回基本统计信息
                pass
            
            result = {
                'timestamp': current_time.isoformat(),
                'total_vms': total_vms,
                'running_vms': running_vms,
                'stopped_vms': stopped_vms,
                'paused_vms': paused_vms,
                'status_changes': status_changes,
                'deleted_vms': deleted_vms,
                'vm_details': vm_status_list
            }
            
            logger.debug(f"监控完成: 总计{total_vms}个虚拟机，运行中{running_vms}个，已停止{stopped_vms}个，已暂停{paused_vms}个")
            return result
            
        except Exception as e:
            logger.error(f"监控虚拟机状态时出错: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'total_vms': 0,
                'running_vms': 0,
                'stopped_vms': 0,
                'paused_vms': 0,
                'status_changes': [],
                'deleted_vms': [],
                'vm_details': []
            }

    def update_selected_directories(self, directories: List[str]) -> bool:
        """
        更新选中的虚拟机目录
        
        Args:
            directories: 目录路径列表
            
        Returns:
            是否成功更新
        """
        try:
            logger.info(f"更新选中的虚拟机目录: {directories}")
            
            # 验证目录是否存在且包含虚拟机文件
            valid_directories = []
            for directory in directories:
                if os.path.exists(directory):
                    # 验证是否包含虚拟机文件
                    if self.validate_vm_directory(directory):
                        valid_directories.append(directory)
                        logger.debug(f"目录有效且包含虚拟机: {directory}")
                    else:
                        logger.warning(f"目录不包含虚拟机文件: {directory}")
                else:
                    logger.warning(f"目录不存在: {directory}")
            
            if not valid_directories:
                logger.error("没有有效的虚拟机目录")
                return False
            
            # 更新配置
            try:
                import config
                config.SELECTED_VM_DIRECTORIES = valid_directories
                logger.info(f"成功更新选中目录: {valid_directories}")
                return True
            except ImportError:
                logger.error("无法导入config模块")
                return False
                
        except Exception as e:
            logger.error(f"更新选中目录时出错: {e}")
            return False

    def scan_directory_for_vms(self, directory_path: str) -> Dict:
        """
        递归扫描目录中的虚拟机文件
        
        Args:
            directory_path: 目录路径
            
        Returns:
            扫描结果字典
        """
        try:
            logger.info(f"开始扫描目录: {directory_path}")
            
            if not os.path.exists(directory_path):
                return {
                    'success': False,
                    'message': f'目录不存在: {directory_path}',
                    'vm_files': [],
                    'total_files': 0
                }
            
            vm_files = []
            total_files = 0
            vm_extensions = ['.vbox', '.vbox-prev']
            
            # 递归扫描目录
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    total_files += 1
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    
                    if file_ext in vm_extensions:
                        # 获取相对路径
                        rel_path = os.path.relpath(file_path, directory_path)
                        vm_files.append({
                            'name': file,
                            'path': rel_path,
                            'full_path': file_path,
                            'size': os.path.getsize(file_path)
                        })
                        logger.debug(f"发现虚拟机文件: {rel_path}")
            
            result = {
                'success': True,
                'message': f'扫描完成，发现 {len(vm_files)} 个虚拟机文件',
                'vm_files': vm_files,
                'total_files': total_files,
                'directory': directory_path
            }
            
            logger.info(f"扫描完成: 总计 {total_files} 个文件，发现 {len(vm_files)} 个虚拟机文件")
            return result
            
        except Exception as e:
            logger.error(f"扫描目录 {directory_path} 时出错: {e}")
            return {
                'success': False,
                'message': f'扫描目录失败: {str(e)}',
                'vm_files': [],
                'total_files': 0
            }

    def validate_vm_directory(self, directory_path: str) -> bool:
        """
        验证目录是否包含虚拟机文件
        
        Args:
            directory_path: 目录路径
            
        Returns:
            是否包含虚拟机文件
        """
        try:
            scan_result = self.scan_directory_for_vms(directory_path)
            return scan_result['success'] and len(scan_result['vm_files']) > 0
        except Exception as e:
            logger.error(f"验证目录 {directory_path} 时出错: {e}")
            return False

    def mark_start_failure(self, vm_name: str):
        """
        标记虚拟机启动失败
        
        Args:
            vm_name: 虚拟机名称
        """
        try:
            if not hasattr(self, 'start_failures'):
                self.start_failures = {}
            
            if vm_name not in self.start_failures:
                self.start_failures[vm_name] = {
                    'count': 0,
                    'first_failure': datetime.now().isoformat(),
                    'last_failure': datetime.now().isoformat()
                }
            
            self.start_failures[vm_name]['count'] += 1
            self.start_failures[vm_name]['last_failure'] = datetime.now().isoformat()
            
            logger.warning(f"标记虚拟机 {vm_name} 启动失败，失败次数: {self.start_failures[vm_name]['count']}")
            
        except Exception as e:
            logger.error(f"标记启动失败时出错: {e}")

    def clear_start_failure(self, vm_name: str):
        """
        清除虚拟机启动失败标记
        
        Args:
            vm_name: 虚拟机名称
        """
        try:
            if hasattr(self, 'start_failures') and vm_name in self.start_failures:
                del self.start_failures[vm_name]
                logger.info(f"清除虚拟机 {vm_name} 启动失败标记")
        except Exception as e:
            logger.error(f"清除启动失败标记时出错: {e}")

    def get_start_failures(self) -> Dict:
        """
        获取所有启动失败信息
        
        Returns:
            启动失败信息字典
        """
        return getattr(self, 'start_failures', {})
    
    def mark_vm_exception(self, vm_name: str, operation: str, error_message: str):
        """
        标记虚拟机异常状态
        
        Args:
            vm_name: 虚拟机名称
            operation: 操作类型 (start/stop)
            error_message: 错误信息
        """
        timestamp = datetime.now().isoformat()
        self.vm_exceptions[vm_name] = {
            'operation': operation,
            'error_message': error_message,
            'timestamp': timestamp,
            'count': self.vm_exceptions.get(vm_name, {}).get('count', 0) + 1
        }
        logger.warning(f"虚拟机 {vm_name} {operation} 操作异常: {error_message}")
    
    def clear_vm_exception(self, vm_name: str):
        """
        清除虚拟机异常状态
        
        Args:
            vm_name: 虚拟机名称
        """
        if vm_name in self.vm_exceptions:
            del self.vm_exceptions[vm_name]
            logger.info(f"已清除虚拟机 {vm_name} 的异常状态")
    
    def get_vm_exceptions(self) -> Dict:
        """
        获取所有虚拟机异常状态
        
        Returns:
            Dict: 异常状态字典
        """
        return self.vm_exceptions.copy()
    
    def get_vm_exception_status(self, vm_name: str) -> Optional[Dict]:
        """
        获取指定虚拟机的异常状态
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            Optional[Dict]: 异常状态信息，如果没有异常则返回None
        """
        return self.vm_exceptions.get(vm_name)
    
    def mark_vm_as_deleted(self, vm_name: str):
        """标记虚拟机为已删除状态"""
        try:
            # 加载已删除虚拟机列表
            deleted_vms = self.load_deleted_vms()
            if vm_name not in deleted_vms:
                deleted_vms.append(vm_name)
                self.save_deleted_vms(deleted_vms)
                logger.info(f"虚拟机 {vm_name} 已标记为删除状态")
        except Exception as e:
            logger.error(f"标记虚拟机 {vm_name} 为删除状态失败: {e}")
    
    def is_vm_deleted(self, vm_name: str) -> bool:
        """检查虚拟机是否已被删除（从备份目录检查）"""
        try:
            # 获取备份目录路径
            from config import get_backup_directory_path
            backup_dir = get_backup_directory_path()
            
            if not os.path.exists(backup_dir):
                logger.debug(f"备份目录不存在: {backup_dir}")
                return False
            
            # 检查虚拟机目录是否存在于备份目录中
            vm_backup_path = os.path.join(backup_dir, vm_name)
            if os.path.exists(vm_backup_path) and os.path.isdir(vm_backup_path):
                # 检查是否包含.vbox文件（确认是虚拟机目录）
                vbox_files = [f for f in os.listdir(vm_backup_path) if f.endswith('.vbox')]
                if vbox_files:
                    logger.debug(f"虚拟机 {vm_name} 在备份目录中找到")
                    return True
            
            logger.debug(f"虚拟机 {vm_name} 在备份目录中未找到")
            return False
            
        except Exception as e:
            logger.error(f"检查虚拟机 {vm_name} 删除状态失败: {e}")
            # 如果从备份目录检查失败，回退到JSON文件
            try:
                deleted_vms = self.load_deleted_vms()
                return vm_name in deleted_vms
            except Exception as e2:
                logger.error(f"回退到JSON文件检查也失败: {e2}")
                return False
    
    def load_deleted_vms(self) -> List[str]:
        """加载已删除虚拟机列表"""
        try:
            deleted_vms_file = os.path.join(os.path.dirname(__file__), 'deleted_vms.json')
            if os.path.exists(deleted_vms_file):
                with open(deleted_vms_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"加载已删除虚拟机列表失败: {e}")
            return []
    
    def save_deleted_vms(self, deleted_vms: List[str]):
        """保存已删除虚拟机列表"""
        try:
            deleted_vms_file = os.path.join(os.path.dirname(__file__), 'deleted_vms.json')
            with open(deleted_vms_file, 'w', encoding='utf-8') as f:
                json.dump(deleted_vms, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存已删除虚拟机列表失败: {e}")
    

    
    def _get_directory_size(self, directory_path: str) -> float:
        """计算目录大小（MB）"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(directory_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            return round(total_size / (1024 * 1024), 2)  # 转换为MB
        except Exception as e:
            logger.warning(f"计算目录大小失败: {e}")
            return 0.0

    def _handle_vbox_service_issue(self, vm_name: str, operation: str, error: Exception):
        """
        处理VirtualBox服务问题
        
        Args:
            vm_name: 虚拟机名称
            operation: 操作类型
            error: 错误信息
        """
        error_msg = f"VirtualBox服务问题 - {operation} 操作失败: {str(error)}"
        logger.error(f"虚拟机 {vm_name} {error_msg}")
        monitor_logger.error(f"虚拟机 {vm_name} {error_msg}")
        
        # 标记异常状态
        self.mark_vm_exception(vm_name, operation, error_msg)
        
        # 尝试重启VirtualBox服务（仅在Windows上）
        if os.name == 'nt':
            try:
                # 从配置文件获取超时时间
                from config import VM_STATUS_TIMEOUT
                service_restart_timeout = min(VM_STATUS_TIMEOUT, 15)  # 服务重启使用较长超时
                
                logger.info("尝试重启VirtualBox服务...")
                subprocess.run(['net', 'stop', 'VBoxSvc'], capture_output=True, timeout=service_restart_timeout)
                import time
                time.sleep(2)
                subprocess.run(['net', 'start', 'VBoxSvc'], capture_output=True, timeout=service_restart_timeout)
                logger.info("VirtualBox服务重启完成")
                monitor_logger.info("VirtualBox服务重启完成")
            except Exception as e:
                logger.warning(f"重启VirtualBox服务失败: {e}")
                monitor_logger.warning(f"重启VirtualBox服务失败: {e}")

    # 移除VirtualBox服务健康检查方法
    
    # 移除VirtualBox服务恢复方法
    
    # 移除强制杀死VirtualBox进程方法
    
    # 移除激进恢复VirtualBox服务方法
    
    # 移除启动时VirtualBox服务状态检查方法

    def load_vm_config(self):
        """加载虚拟机配置文件"""
        try:
            # 从配置文件加载自动删除配置
            try:
                from config import (
                    AUTO_DELETE_ENABLED, 
                    AUTO_DELETE_MAX_COUNT, 
                    AUTO_DELETE_BACKUP_DIR,
                    AUTO_DELETE_BACKUP_STRATEGY,
                    AUTO_DELETE_BACKUP_LOCATION,
                    get_backup_directory_path
                )
                self.auto_delete_enabled = AUTO_DELETE_ENABLED
                self.max_start_count = AUTO_DELETE_MAX_COUNT
                self.delete_backup_dir = AUTO_DELETE_BACKUP_DIR
                self.backup_strategy = AUTO_DELETE_BACKUP_STRATEGY
                self.backup_location = AUTO_DELETE_BACKUP_LOCATION
                self.get_backup_path = get_backup_directory_path
                
                logger.info(f"从配置文件加载自动删除配置:")
                logger.info(f"  - 启用状态: {self.auto_delete_enabled}")
                logger.info(f"  - 最大次数: {self.max_start_count}")
                logger.info(f"  - 备份目录名称: {self.delete_backup_dir}")
                logger.info(f"  - 备份策略: {self.backup_strategy}")
                logger.info(f"  - 备份位置: {self.backup_location}")
                
                # 计算实际备份路径
                actual_backup_path = get_backup_directory_path()
                logger.info(f"  - 实际备份路径: {actual_backup_path}")
                
            except ImportError as e:
                logger.warning(f"无法从配置文件加载自动删除配置: {e}，使用默认值")
                self.auto_delete_enabled = False
                self.max_start_count = 10
                self.delete_backup_dir = "delete_bak"
                self.backup_strategy = "dynamic"
                self.backup_location = "sibling"
            
            if os.path.exists(self.vm_config_file):
                with open(self.vm_config_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        # 只读取虚拟机启动次数配置，自动删除配置从config.py读取
                        if not line.startswith('AUTO_DELETE_') and not line.startswith('MAX_START_COUNT') and not line.startswith('DELETE_BACKUP_DIR'):
                            # 虚拟机启动次数配置
                            vm_name, count = line.split('=', 1)
                            self.vm_start_counts[vm_name.strip()] = int(count.strip())
                
                logger.info(f"加载虚拟机配置成功，共 {len(self.vm_start_counts)} 个虚拟机")
            else:
                # 创建默认配置文件（只包含虚拟机启动次数）
                self.save_vm_config()
                logger.info("创建默认虚拟机配置文件")
                
        except Exception as e:
            logger.error(f"加载虚拟机配置文件失败: {e}")
            self.auto_delete_enabled = False
            self.max_start_count = 10
            self.delete_backup_dir = "delete_bak"

    def save_vm_config(self):
        """保存虚拟机配置文件"""
        try:
            with open(self.vm_config_file, 'w', encoding='utf-8') as f:
                f.write("# 虚拟机启动次数配置文件\n")
                f.write("# 格式: 虚拟机名称 = 启动次数\n\n")
                
                # 写入虚拟机启动次数
                for vm_name, count in self.vm_start_counts.items():
                    f.write(f"{vm_name} = {count}\n")
            
            logger.info("保存虚拟机配置文件成功")
            
        except Exception as e:
            logger.error(f"保存虚拟机配置文件失败: {e}")

    def increment_vm_start_count(self, vm_name: str):
        """增加虚拟机启动次数"""
        if vm_name not in self.vm_start_counts:
            self.vm_start_counts[vm_name] = 0
        
        self.vm_start_counts[vm_name] += 1
        logger.info(f"虚拟机 {vm_name} 启动次数增加到: {self.vm_start_counts[vm_name]}")
        
        # 保存配置
        self.save_vm_config()

    def get_vm_start_count(self, vm_name: str) -> int:
        """获取虚拟机启动次数"""
        return self.vm_start_counts.get(vm_name, 0)

    def set_auto_delete_config(self, enabled: bool, max_count: int, backup_dir: str):
        """设置自动删除配置"""
        try:
            # 更新config.py文件
            config_content = ""
            with open('config.py', 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines):
                    if line.strip().startswith('AUTO_DELETE_ENABLED ='):
                        lines[i] = f"AUTO_DELETE_ENABLED = {enabled}"
                    elif line.strip().startswith('AUTO_DELETE_MAX_COUNT ='):
                        lines[i] = f"AUTO_DELETE_MAX_COUNT = {max_count}"
                    elif line.strip().startswith('AUTO_DELETE_BACKUP_DIR ='):
                        lines[i] = f'AUTO_DELETE_BACKUP_DIR = "{backup_dir}"'
                
                config_content = '\n'.join(lines)
            
            with open('config.py', 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            # 更新内存中的配置
            self.auto_delete_enabled = enabled
            self.max_start_count = max_count
            self.delete_backup_dir = backup_dir
            
            logger.info(f"更新自动删除配置: 启用={enabled}, 最大次数={max_count}, 备份目录={backup_dir}")
            
        except Exception as e:
            logger.error(f"更新自动删除配置失败: {e}")
            # 如果更新配置文件失败，至少更新内存中的配置
            self.auto_delete_enabled = enabled
            self.max_start_count = max_count
            self.delete_backup_dir = backup_dir

    def auto_delete_vm(self, vm_name: str) -> bool:
        """自动删除虚拟机（实际为移动虚拟机文件）"""
        try:
            # 打印详细的删除开始日志
            logger.info("=" * 60)
            logger.info(f"🚀 开始自动删除虚拟机: {vm_name}")
            logger.info(f"⏰ 删除时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            monitor_logger.info("=" * 60)
            monitor_logger.info(f"🚀 开始自动删除虚拟机: {vm_name}")
            monitor_logger.info(f"⏰ 删除时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 强制刷新日志输出
            import sys
            sys.stdout.flush()
            
            # 检查自动删除是否启用
            logger.info(f"📋 检查自动删除配置...")
            if not self.auto_delete_enabled:
                logger.warning(f"❌ 自动删除功能未启用，跳过虚拟机 {vm_name}")
                monitor_logger.warning(f"❌ 自动删除功能未启用，跳过虚拟机 {vm_name}")
                return False
            logger.info(f"✅ 自动删除功能已启用")
            
            # 检查监控是否启用（通过配置文件检查）
            logger.info(f"📋 检查监控状态...")
            try:
                from config import AUTO_MONITOR_BUTTON_ENABLED
                if not AUTO_MONITOR_BUTTON_ENABLED:
                    logger.warning(f"❌ 监控功能未启用，跳过自动删除虚拟机 {vm_name}")
                    monitor_logger.warning(f"❌ 监控功能未启用，跳过自动删除虚拟机 {vm_name}")
                    return False
                logger.info(f"✅ 监控功能已启用")
            except ImportError:
                logger.warning(f"⚠️ 无法检查监控状态，跳过自动删除虚拟机 {vm_name}")
                monitor_logger.warning(f"⚠️ 无法检查监控状态，跳过自动删除虚拟机 {vm_name}")
                return False
            
            # 检查启动次数是否达到阈值
            current_count = self.vm_start_counts.get(vm_name, 0)
            logger.info(f"📊 虚拟机 {vm_name} 当前启动次数: {current_count}")
            logger.info(f"📊 删除阈值: {self.max_start_count}")
            
            if current_count < self.max_start_count:
                logger.warning(f"❌ 虚拟机 {vm_name} 启动次数 {current_count} 未达到删除阈值 {self.max_start_count}")
                monitor_logger.warning(f"❌ 虚拟机 {vm_name} 启动次数 {current_count} 未达到删除阈值 {self.max_start_count}")
                return False
            
            logger.info(f"✅ 虚拟机 {vm_name} 启动次数已达到删除阈值，开始删除流程")
            
            # 首先停止虚拟机
            logger.info(f"🛑 开始停止虚拟机 {vm_name}...")
            monitor_logger.info(f"🛑 开始停止虚拟机 {vm_name}...")
            
            # 添加更详细的停止过程日志
            try:
                logger.info(f"🛑 开始执行停止虚拟机 {vm_name} 命令...")
                monitor_logger.info(f"🛑 开始执行停止虚拟机 {vm_name} 命令...")
                
                stop_result = self.stop_vm(vm_name)
                
                logger.info(f"🔄 停止虚拟机 {vm_name} 操作完成，结果: {stop_result}")
                monitor_logger.info(f"🔄 停止虚拟机 {vm_name} 操作完成，结果: {stop_result}")
                
                if not stop_result:
                    logger.warning(f"⚠️ 停止虚拟机 {vm_name} 失败，但继续删除流程")
                    monitor_logger.warning(f"⚠️ 停止虚拟机 {vm_name} 失败，但继续删除流程")
                else:
                    logger.info(f"✅ 虚拟机 {vm_name} 停止成功")
                    monitor_logger.info(f"✅ 虚拟机 {vm_name} 停止成功")
                    
                # 强制刷新日志输出
                import sys
                sys.stdout.flush()
                
            except Exception as e:
                logger.error(f"❌ 停止虚拟机 {vm_name} 时发生异常: {e}")
                monitor_logger.error(f"❌ 停止虚拟机 {vm_name} 时发生异常: {e}")
                # 即使停止失败，也继续删除流程
                stop_result = False
            
            # 等待一段时间确保虚拟机完全停止
            logger.info(f"⏳ 等待虚拟机完全停止...")
            import time
            time.sleep(3)
            logger.info(f"✅ 等待完成")
            
            # 创建备份目录（使用新的配置系统）
            try:
                from config import get_backup_directory_path
                backup_dir = get_backup_directory_path()
                logger.info(f"📁 备份目录路径: {backup_dir}")
                logger.info(f"📋 备份策略: {getattr(self, 'backup_strategy', 'dynamic')}")
                logger.info(f"📋 备份位置: {getattr(self, 'backup_location', 'sibling')}")
            except ImportError:
                # 如果无法导入新配置，使用旧逻辑
                backup_dir = os.path.join(os.path.dirname(self.vbox_dir), self.delete_backup_dir)
                logger.info(f"📁 使用旧配置备份目录路径: {backup_dir}")
            
            if not os.path.exists(backup_dir):
                logger.info(f"📁 创建备份目录: {backup_dir}")
                monitor_logger.info(f"📁 创建备份目录: {backup_dir}")
                os.makedirs(backup_dir)
                logger.info(f"✅ 备份目录创建成功")
            else:
                logger.info(f"✅ 备份目录已存在")
            
            # 查找虚拟机目录（支持递归查找）
            vm_path = self._get_vm_path(vm_name)
            logger.info(f"📁 虚拟机路径: {vm_path}")
            
            # 确定虚拟机目录（如果返回的是.vbox文件，则获取其目录）
            if vm_path.endswith('.vbox'):
                vm_dir = os.path.dirname(vm_path)
            else:
                vm_dir = vm_path
            
            logger.info(f"📁 虚拟机目录路径: {vm_dir}")
            
            if not os.path.exists(vm_dir):
                logger.error(f"❌ 虚拟机目录不存在: {vm_dir}")
                monitor_logger.error(f"❌ 虚拟机目录不存在: {vm_dir}")
                return False
            
            logger.info(f"✅ 虚拟机目录存在，大小: {self._get_directory_size(vm_dir)} MB")
            
            # 移动虚拟机目录到备份目录
            backup_path = os.path.join(backup_dir, vm_name)
            logger.info(f"📁 目标备份路径: {backup_path}")
            
            if os.path.exists(backup_path):
                # 如果备份目录已存在，添加时间戳
                timestamp = int(time.time())
                backup_path = f"{backup_path}_{timestamp}"
                logger.info(f"📁 备份目录已存在，使用时间戳命名: {backup_path}")
                monitor_logger.info(f"📁 备份目录已存在，使用时间戳命名: {backup_path}")
            
            # 移动目录
            logger.info(f"🔄 开始移动虚拟机文件...")
            monitor_logger.info(f"🔄 开始移动虚拟机文件...")
            
            # 强制刷新日志输出
            import sys
            sys.stdout.flush()
            
            import shutil
            shutil.move(vm_dir, backup_path)
            
            logger.info(f"✅ 虚拟机 {vm_name} 已成功移动到备份目录: {backup_path}")
            monitor_logger.info(f"✅ 虚拟机 {vm_name} 已成功移动到备份目录: {backup_path}")
            
            # 强制刷新日志输出
            sys.stdout.flush()
            
            # 标记虚拟机为已删除状态
            logger.info(f"🏷️ 标记虚拟机为已删除状态...")
            self.mark_vm_as_deleted(vm_name)
            logger.info(f"✅ 虚拟机 {vm_name} 已标记为删除状态")
            
            # 从配置中移除启动次数记录
            if vm_name in self.vm_start_counts:
                logger.info(f"🗑️ 从配置中移除虚拟机 {vm_name} 的启动次数记录...")
                del self.vm_start_counts[vm_name]
                self.save_vm_config()
                logger.info(f"✅ 已从配置中移除虚拟机 {vm_name} 的启动次数记录")
            
            # 打印删除完成日志
            logger.info(f"🎉 虚拟机 {vm_name} 自动删除完成！")
            logger.info(f"📁 备份位置: {backup_path}")
            logger.info(f"📊 删除原因: 启动次数 {current_count} 已达到阈值 {self.max_start_count}")
            logger.info("=" * 60)
            monitor_logger.info(f"🎉 虚拟机 {vm_name} 自动删除完成！")
            monitor_logger.info(f"📁 备份位置: {backup_path}")
            monitor_logger.info(f"📊 删除原因: 启动次数 {current_count} 已达到阈值 {self.max_start_count}")
            monitor_logger.info("=" * 60)
            
            # 强制刷新日志输出
            sys.stdout.flush()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 自动删除虚拟机 {vm_name} 失败: {e}")
            monitor_logger.error(f"❌ 自动删除虚拟机 {vm_name} 失败: {e}")
            logger.error("=" * 60)
            monitor_logger.error("=" * 60)
            return False





# 全局监控器实例
vbox_monitor = None

def get_vbox_monitor() -> VirtualBoxMonitor:
    """获取全局VirtualBox监控器实例"""
    global vbox_monitor
    if vbox_monitor is None:
        vbox_monitor = VirtualBoxMonitor()
    return vbox_monitor

if __name__ == "__main__":
    # 测试代码
    monitor = VirtualBoxMonitor()
    
    print("=== VirtualBox虚拟机监控测试 ===")
    
    # 扫描虚拟机
    print("\n1. 扫描虚拟机...")
    vms = monitor.scan_vms()
    print(f"发现 {len(vms)} 个虚拟机")
    
    # 获取状态
    print("\n2. 获取虚拟机状态...")
    for vm in vms:
        status = monitor.get_vm_status(vm['name'])
        print(f"{vm['name']}: {status}")
    
    # 自动启动测试
    print("\n3. 自动启动已停止的虚拟机...")
    results = monitor.auto_start_stopped_vms()
    for result in results:
        print(f"{result['name']}: {'成功' if result['success'] else '失败'}")
    
    print("\n测试完成") 