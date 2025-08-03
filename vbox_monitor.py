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
from datetime import datetime
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
    LOG_FILE = "vbox_monitor.log"
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
    LOG_ENCODING = "utf-8"
    VM_STATUS_TIMEOUT = 10
    VM_START_TIMEOUT = 60
    VM_STOP_TIMEOUT = 30
    SCAN_VMS_TIMEOUT = 10
    VM_INFO_TIMEOUT = 10
    VERBOSE_LOGGING = True
    AUTO_START_STOPPED_VMS = True
    MONITOR_THREAD_DAEMON = True

# 配置主日志
log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding=LOG_ENCODING),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 配置监控专用日志
try:
    from config import MONITOR_LOG_FILE, MONITOR_LOG_LEVEL, MONITOR_LOG_FORMAT, MONITOR_LOG_ENCODING, MONITOR_VERBOSE_LOGGING
    monitor_log_level = getattr(logging, MONITOR_LOG_LEVEL.upper(), logging.DEBUG)
    
    # 创建监控日志处理器
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
        
        logger.info(f"VirtualBox监控器初始化完成")
        logger.info(f"虚拟机目录: {self.vbox_dir}")
        logger.info(f"VBoxManage路径: {self.vboxmanage_path}")
        
        # 监控日志记录
        monitor_logger.info(f"VirtualBox监控器初始化完成")
        monitor_logger.info(f"虚拟机目录: {self.vbox_dir}")
        monitor_logger.info(f"VBoxManage路径: {self.vboxmanage_path}")
        logger.info(f"日志级别: {LOG_LEVEL}")
        logger.info(f"启动类型: {VBOX_START_TYPE}")
    
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
                        capture_output=True, timeout=10
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
                                  capture_output=True, timeout=5)
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
    
    def scan_vms(self) -> List[Dict]:
        """
        扫描虚拟机目录，发现所有虚拟机
        
        Returns:
            虚拟机信息列表
        """
        vms = []
        
        logger.debug(f"开始扫描虚拟机，VBoxManage路径: {self.vboxmanage_path}")
        logger.debug(f"虚拟机目录: {self.vbox_dir}")
        
        if not os.path.exists(self.vbox_dir):
            logger.warning(f"虚拟机目录不存在: {self.vbox_dir}")
            logger.info("尝试使用VBoxManage命令获取虚拟机列表...")
            # 即使目录不存在，也尝试通过VBoxManage命令获取虚拟机列表
        else:
            logger.info(f"扫描虚拟机目录: {self.vbox_dir}")
        
        try:
            # 使用VBoxManage list vms命令获取所有虚拟机
            logger.debug(f"执行命令: {self.vboxmanage_path} list vms")
            result = subprocess.run(
                [self.vboxmanage_path, 'list', 'vms'],
                capture_output=True, timeout=SCAN_VMS_TIMEOUT
            )
            
            # 手动处理编码
            logger.debug(f"命令执行结果 - 返回码: {result.returncode}")
            if result.returncode == 0:
                try:
                    stdout = result.stdout.decode('utf-8', errors='ignore')
                    logger.debug("使用UTF-8编码解码成功")
                except UnicodeDecodeError:
                    try:
                        stdout = result.stdout.decode('gbk', errors='ignore')
                        logger.debug("使用GBK编码解码成功")
                    except UnicodeDecodeError:
                        stdout = result.stdout.decode('latin-1', errors='ignore')
                        logger.debug("使用Latin-1编码解码成功")
            else:
                stdout = ""
                logger.warning(f"命令执行失败，返回码: {result.returncode}")
                try:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                    logger.debug(f"错误输出: {stderr}")
                except:
                    pass
            
            if result.returncode == 0:
                lines = stdout.strip().split('\n')
                logger.debug(f"解析到 {len(lines)} 行输出")
                for line in lines:
                    if line.strip():
                        logger.debug(f"处理行: {line.strip()}")
                        # 解析虚拟机信息，格式: "VM名称" {UUID}
                        parts = line.strip().split(' {')
                        if len(parts) == 2:
                            vm_name = parts[0].strip('"')
                            vm_uuid = parts[1].strip('}')
                            
                            logger.debug(f"解析虚拟机: 名称={vm_name}, UUID={vm_uuid}")
                            
                            vm_info = {
                                'name': vm_name,
                                'uuid': vm_uuid,
                                'path': self._get_vm_path(vm_name),
                                'status': 'unknown'
                            }
                            vms.append(vm_info)
                            logger.info(f"发现虚拟机: {vm_name} ({vm_uuid})")
                        else:
                            logger.debug(f"无法解析行: {line.strip()}")
            
        except subprocess.TimeoutExpired:
            logger.error(f"扫描虚拟机超时 ({SCAN_VMS_TIMEOUT}秒)")
        except Exception as e:
            if VERBOSE_LOGGING:
                logger.error(f"扫描虚拟机时出错: {e}")
            else:
                logger.error("扫描虚拟机时出错")
        
        return vms
    
    def _get_vm_path(self, vm_name: str) -> str:
        """获取虚拟机文件路径"""
        # 首先尝试从VBoxManage获取虚拟机信息
        try:
            result = subprocess.run(
                [self.vboxmanage_path, 'showvminfo', vm_name, '--machinereadable'],
                capture_output=True, timeout=10
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
        
        # 如果无法获取，使用默认路径
        vm_dir = os.path.join(self.vbox_dir, vm_name)
        vbox_file = os.path.join(vm_dir, f"{vm_name}.vbox")
        
        if os.path.exists(vbox_file):
            return vbox_file
        else:
            return vm_dir
    
    def get_vm_status(self, vm_name: str) -> str:
        """
        获取虚拟机状态
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            虚拟机状态: running, poweroff, paused, saved, aborted, unknown
        """
        logger.debug(f"开始获取虚拟机 {vm_name} 状态")
        try:
            logger.debug(f"执行命令: {self.vboxmanage_path} showvminfo {vm_name} --machinereadable")
            result = subprocess.run(
                [self.vboxmanage_path, 'showvminfo', vm_name, '--machinereadable'],
                capture_output=True, timeout=VM_STATUS_TIMEOUT
            )
            
            # 手动处理编码
            logger.debug(f"命令执行结果 - 返回码: {result.returncode}")
            try:
                stdout = result.stdout.decode('utf-8', errors='ignore')
                logger.debug("使用UTF-8编码解码成功")
            except UnicodeDecodeError:
                try:
                    stdout = result.stdout.decode('gbk', errors='ignore')
                    logger.debug("使用GBK编码解码成功")
                except UnicodeDecodeError:
                    stdout = result.stdout.decode('latin-1', errors='ignore')
                    logger.debug("使用Latin-1编码解码成功")
            
            if result.returncode == 0:
                lines = stdout.strip().split('\n')
                logger.debug(f"解析到 {len(lines)} 行输出")
                logger.debug(f"前5行输出:")
                for i, line in enumerate(lines[:5]):
                    logger.debug(f"  {i+1}: {line}")
                
                for line in lines:
                    if line.startswith('VMState='):
                        # 正确处理状态值，去除所有引号
                        status = line.split('=', 1)[1].strip().strip('"')
                        logger.debug(f"找到VMState行: {line.strip()}")
                        logger.debug(f"虚拟机 {vm_name} 原始状态: {status}")
                        
                        # VirtualBox状态映射
                        status_mapping = {
                            'running': 'running',
                            'poweroff': 'poweroff', 
                            'paused': 'paused',
                            'saved': 'saved',
                            'aborted': 'aborted',
                            'starting': 'running',  # 启动中视为运行中
                            'stopping': 'poweroff', # 停止中视为已关闭
                            'saving': 'saved',      # 保存中视为已保存
                            'restoring': 'running', # 恢复中视为运行中
                            # 可能的中文状态
                            '正在运行': 'running',
                            '已关闭': 'poweroff',
                            '已暂停': 'paused',
                            '已保存': 'saved',
                            '异常终止': 'aborted'
                        }
                        
                        mapped_status = status_mapping.get(status, 'unknown')
                        logger.debug(f"虚拟机 {vm_name} 映射后状态: {mapped_status}")
                        return mapped_status
                
                # 如果没有找到VMState，尝试其他方法
                logger.warning(f"虚拟机 {vm_name} 未找到VMState信息")
                # 尝试使用running命令检查
                try:
                    running_result = subprocess.run(
                        [self.vboxmanage_path, 'list', 'runningvms'],
                        capture_output=True, timeout=5
                    )
                    if running_result.returncode == 0:
                        try:
                            running_stdout = running_result.stdout.decode('utf-8', errors='ignore')
                        except UnicodeDecodeError:
                            running_stdout = running_result.stdout.decode('gbk', errors='ignore')
                        
                        if vm_name in running_stdout:
                            logger.debug(f"虚拟机 {vm_name} 在运行列表中")
                            return 'running'
                except:
                    pass
                
                return 'unknown'
            else:
                logger.warning(f"获取虚拟机 {vm_name} 状态失败，返回码: {result.returncode}")
                # 尝试从错误输出中获取信息
                try:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                    logger.debug(f"错误信息: {stderr}")
                except:
                    pass
            
        except subprocess.TimeoutExpired:
            logger.error(f"获取虚拟机 {vm_name} 状态超时 ({VM_STATUS_TIMEOUT}秒)")
        except Exception as e:
            if VERBOSE_LOGGING:
                logger.error(f"获取虚拟机 {vm_name} 状态时出错: {e}")
            else:
                logger.error(f"获取虚拟机 {vm_name} 状态时出错")
        
        return 'unknown'
    
    def start_vm(self, vm_name: str) -> bool:
        """
        启动虚拟机
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            是否成功启动
        """
        try:
            logger.info(f"正在启动虚拟机: {vm_name}")
            result = subprocess.run(
                [self.vboxmanage_path, 'startvm', vm_name, '--type', VBOX_START_TYPE],
                capture_output=True, timeout=VM_START_TIMEOUT
            )
            
            # 手动处理编码
            if result.returncode == 0:
                try:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stderr = result.stderr.decode('gbk', errors='ignore')
                    except UnicodeDecodeError:
                        stderr = result.stderr.decode('latin-1', errors='ignore')
            else:
                try:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stderr = result.stderr.decode('gbk', errors='ignore')
                    except UnicodeDecodeError:
                        stderr = result.stderr.decode('latin-1', errors='ignore')
            
            if result.returncode == 0:
                logger.info(f"虚拟机 {vm_name} 启动成功")
                # 清除异常状态
                self.clear_vm_exception(vm_name)
                return True
            else:
                error_msg = f"启动失败: {stderr}"
                logger.error(f"虚拟机 {vm_name} {error_msg}")
                # 标记异常状态
                self.mark_vm_exception(vm_name, 'start', error_msg)
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"启动虚拟机 {vm_name} 超时 ({VM_START_TIMEOUT}秒)")
            return False
        except Exception as e:
            if VERBOSE_LOGGING:
                logger.error(f"启动虚拟机 {vm_name} 时出错: {e}")
            else:
                logger.error(f"启动虚拟机 {vm_name} 时出错")
            return False
    
    def stop_vm(self, vm_name: str) -> bool:
        """
        停止虚拟机
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            是否成功停止
        """
        try:
            logger.info(f"正在停止虚拟机: {vm_name}")
            result = subprocess.run(
                [self.vboxmanage_path, 'controlvm', vm_name, 'poweroff'],
                capture_output=True, timeout=30
            )
            
            # 手动处理编码
            if result.returncode == 0:
                try:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stderr = result.stderr.decode('gbk', errors='ignore')
                    except UnicodeDecodeError:
                        stderr = result.stderr.decode('latin-1', errors='ignore')
            else:
                try:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stderr = result.stderr.decode('gbk', errors='ignore')
                    except UnicodeDecodeError:
                        stderr = result.stderr.decode('latin-1', errors='ignore')
            
            if result.returncode == 0:
                logger.info(f"虚拟机 {vm_name} 停止成功")
                # 清除异常状态
                self.clear_vm_exception(vm_name)
                return True
            else:
                error_msg = f"停止失败: {stderr}"
                logger.error(f"虚拟机 {vm_name} {error_msg}")
                # 标记异常状态
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
        强制重启虚拟机
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            是否成功重启
        """
        try:
            logger.info(f"正在强制重启虚拟机: {vm_name}")
            
            # 首先强制停止虚拟机
            logger.debug(f"强制停止虚拟机: {vm_name}")
            stop_result = subprocess.run(
                [self.vboxmanage_path, 'controlvm', vm_name, 'poweroff'],
                capture_output=True, timeout=30
            )
            
            if stop_result.returncode != 0:
                logger.warning(f"强制停止虚拟机 {vm_name} 失败，但继续重启流程")
                try:
                    stderr = stop_result.stderr.decode('utf-8', errors='ignore')
                    logger.debug(f"停止错误信息: {stderr}")
                except:
                    pass
            
            # 等待一段时间确保虚拟机完全停止
            import time
            time.sleep(3)
            
            # 然后启动虚拟机
            logger.debug(f"启动虚拟机: {vm_name}")
            start_result = subprocess.run(
                [self.vboxmanage_path, 'startvm', vm_name, '--type', VBOX_START_TYPE],
                capture_output=True, timeout=VM_START_TIMEOUT
            )
            
            # 手动处理编码
            if start_result.returncode == 0:
                try:
                    stderr = start_result.stderr.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stderr = start_result.stderr.decode('gbk', errors='ignore')
                    except UnicodeDecodeError:
                        stderr = start_result.stderr.decode('latin-1', errors='ignore')
            else:
                try:
                    stderr = start_result.stderr.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stderr = start_result.stderr.decode('gbk', errors='ignore')
                    except UnicodeDecodeError:
                        stderr = start_result.stderr.decode('latin-1', errors='ignore')
            
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


    
    def get_all_vm_status(self) -> List[Dict]:
        """
        获取所有虚拟机状态
        
        Returns:
            虚拟机状态列表
        """
        vms = self.scan_vms()
        vm_status_list = []
        start_failures = self.get_start_failures()
        
        for vm in vms:
            status = self.get_vm_status(vm['name'])
            vm_info = {
                'name': vm['name'],
                'uuid': vm['uuid'],
                'path': vm['path'],
                'status': status,
                'last_check': datetime.now().isoformat()
            }
            
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
    
    def auto_start_stopped_vms(self) -> List[Dict]:
        """
        自动启动已停止的虚拟机
        
        Returns:
            启动结果列表
        """
        results = []
        vm_status_list = self.get_all_vm_status()
        
        monitor_logger.info(f"开始自动启动检查，共发现 {len(vm_status_list)} 个虚拟机")
        
        for vm in vm_status_list:
            if vm['status'] in ['poweroff', 'aborted']:
                logger.info(f"发现已停止的虚拟机: {vm['name']} (状态: {vm['status']})")
                monitor_logger.info(f"发现已停止的虚拟机: {vm['name']} (状态: {vm['status']})")
                
                # 检查是否启用自动启动功能
                if not AUTO_START_STOPPED_VMS:
                    logger.info(f"自动启动功能已禁用，跳过虚拟机: {vm['name']}")
                    monitor_logger.info(f"自动启动功能已禁用，跳过虚拟机: {vm['name']}")
                    continue
                
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
                
                monitor_logger.debug(f"尝试启动虚拟机: {vm['name']}")
                success = self.start_vm(vm['name'])
                result = {
                    'name': vm['name'],
                    'original_status': vm['status'],
                    'action': 'start',
                    'success': success,
                    'timestamp': datetime.now().isoformat()
                }
                results.append(result)
                
                if success:
                    logger.info(f"自动启动虚拟机 {vm['name']} 成功")
                    monitor_logger.info(f"自动启动虚拟机 {vm['name']} 成功")
                else:
                    logger.error(f"自动启动虚拟机 {vm['name']} 失败")
                    monitor_logger.error(f"自动启动虚拟机 {vm['name']} 失败")
                    # 记录启动失败，供前端显示
                    self.mark_start_failure(vm['name'])
        
        monitor_logger.info(f"自动启动检查完成，共处理 {len(results)} 个虚拟机")
        return results
    
    def start_monitoring(self, interval: int = 60, auto_start: bool = True, start_time: str = None):
        """
        开始监控虚拟机
        
        Args:
            interval: 监控间隔（秒）
            auto_start: 是否自动启动未运行的虚拟机
            start_time: 监控启动时间戳
        """
        if self.monitoring:
            logger.warning("监控已在运行中")
            monitor_logger.warning("监控已在运行中")
            return
        
        self.monitoring = True
        self.auto_start_enabled = auto_start
        self.last_monitor_results = []
        self.monitor_start_time = start_time or datetime.now().isoformat()
        
        logger.info(f"自动监控已启动，间隔: {interval}秒，自动启动: {auto_start}")
        monitor_logger.info(f"自动监控已启动，间隔: {interval}秒，自动启动: {auto_start}")
        monitor_logger.info(f"自动监控启动时间: {self.monitor_start_time}")
        monitor_logger.info(f"自动监控状态: 已开启，执行间隔: {interval}秒")
        
        def monitor_task():
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
            
            while self.monitoring:
                try:
                    # 记录本次执行开始时间
                    execution_start_time = time.time()
                    
                    logger.info("执行自动监控检查...")
                    monitor_logger.info("执行自动监控检查...")
                    monitor_logger.info(f"自动监控状态: 正在执行，间隔: {interval}秒")
                    
                    # 获取所有虚拟机状态
                    vm_status_list = self.get_all_vm_status()
                    stopped_vms = [vm for vm in vm_status_list if vm['status'] in ['poweroff', 'aborted']]
                    
                    monitor_logger.debug(f"当前虚拟机状态: 总数={len(vm_status_list)}, 已停止={len(stopped_vms)}")
                    
                    # 记录状态监控结果
                    status_result = {
                        'timestamp': datetime.now().isoformat(),
                        'total_vms': len(vm_status_list),
                        'running_vms': len([vm for vm in vm_status_list if vm['status'] == 'running']),
                        'stopped_vms': len(stopped_vms),
                        'paused_vms': len([vm for vm in vm_status_list if vm['status'] == 'paused']),
                        'auto_start_enabled': self.auto_start_enabled
                    }
                    
                    monitor_logger.info(f"状态监控结果: {status_result}")
                    
                    if stopped_vms and self.auto_start_enabled:
                        logger.info(f"发现 {len(stopped_vms)} 个已停止的虚拟机，开始自动启动...")
                        monitor_logger.info(f"发现 {len(stopped_vms)} 个已停止的虚拟机，开始自动启动...")
                        
                        for vm in stopped_vms:
                            monitor_logger.debug(f"准备启动虚拟机: {vm['name']} (状态: {vm['status']})")
                        
                        results = self.auto_start_stopped_vms()
                        
                        # 保存执行结果
                        self.last_monitor_results = results
                        
                        if results:
                            success_count = sum(1 for r in results if r['success'])
                            logger.info(f"本次检查启动了 {len(results)} 个虚拟机，成功 {success_count} 个")
                            monitor_logger.info(f"本次检查启动了 {len(results)} 个虚拟机，成功 {success_count} 个")
                            
                            # 记录详细的启动结果
                            for result in results:
                                if result['success']:
                                    monitor_logger.info(f"虚拟机 {result['name']} 启动成功")
                                else:
                                    logger.warning(f"虚拟机 {result['name']} 启动失败")
                                    monitor_logger.warning(f"虚拟机 {result['name']} 启动失败")
                        else:
                            logger.info("所有虚拟机状态正常，无需启动")
                            monitor_logger.info("所有虚拟机状态正常，无需启动")
                    elif stopped_vms and not self.auto_start_enabled:
                        logger.info(f"发现 {len(stopped_vms)} 个已停止的虚拟机，但自动启动已禁用")
                        monitor_logger.info(f"发现 {len(stopped_vms)} 个已停止的虚拟机，但自动启动已禁用")
                        monitor_logger.info(f"仅执行状态监控，不进行自动启动操作")
                        self.last_monitor_results = []
                    else:
                        logger.info("所有虚拟机状态正常")
                        monitor_logger.info("所有虚拟机状态正常")
                        self.last_monitor_results = []
                    
                except Exception as e:
                    logger.error(f"监控任务出错: {e}")
                    monitor_logger.error(f"监控任务出错: {e}")
                    self.last_monitor_results = []
                
                # 计算本次执行耗时
                execution_time = time.time() - execution_start_time
                monitor_logger.debug(f"本次监控执行耗时: {execution_time:.2f}秒")
                
                # 计算需要等待的时间，确保严格按照间隔执行
                wait_time = max(0, interval - execution_time)
                if wait_time > 0:
                    monitor_logger.debug(f"自动监控等待 {wait_time:.2f} 秒后执行下次检查")
                    time.sleep(wait_time)
                else:
                    monitor_logger.warning(f"自动监控执行时间 ({execution_time:.2f}秒) 超过了设定间隔 ({interval}秒)，立即执行下次检查")
        
        self.monitor_thread = threading.Thread(target=monitor_task, daemon=MONITOR_THREAD_DAEMON)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        logger.info("自动监控已停止")
        monitor_logger.info("自动监控已停止")
        monitor_logger.info("自动监控状态: 已关闭")
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            monitor_logger.debug("监控线程已停止")
    
    def get_vm_info(self, vm_name: str) -> Optional[Dict]:
        """
        获取虚拟机详细信息
        
        Args:
            vm_name: 虚拟机名称
            
        Returns:
            虚拟机详细信息
        """
        try:
            result = subprocess.run(
                [self.vboxmanage_path, 'showvminfo', vm_name],
                capture_output=True, timeout=10
            )
            
            if result.returncode == 0:
                try:
                    stdout = result.stdout.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stdout = result.stdout.decode('gbk', errors='ignore')
                    except UnicodeDecodeError:
                        stdout = result.stdout.decode('latin-1', errors='ignore')
                
                info = {}
                lines = stdout.strip().split('\n')
                
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip()] = value.strip()
                
                return info
            
        except Exception as e:
            logger.error(f"获取虚拟机 {vm_name} 详细信息时出错: {e}")
        
        return None

    def monitor_vm_status(self) -> Dict:
        """
        监控虚拟机状态
        
        Returns:
            监控结果字典
        """
        try:
            logger.debug("开始监控虚拟机状态")
            
            # 获取所有虚拟机状态
            vm_status_list = self.get_all_vm_status()
            
            # 统计信息
            total_vms = len(vm_status_list)
            running_vms = len([vm for vm in vm_status_list if vm['status'] == 'running'])
            stopped_vms = len([vm for vm in vm_status_list if vm['status'] in ['poweroff', 'aborted']])
            paused_vms = len([vm for vm in vm_status_list if vm['status'] == 'paused'])
            
            # 检查状态变化
            status_changes = []
            current_time = datetime.now()
            
            for vm in vm_status_list:
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