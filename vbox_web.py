#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VirtualBox虚拟机监控Web应用
提供Web界面和API接口来管理VirtualBox虚拟机
"""

import json
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from functools import wraps
import os
import time
import subprocess
import sys
import importlib
import threading
from datetime import datetime, timedelta

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vbox_monitor import get_vbox_monitor, VirtualBoxMonitor

# 登录认证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from config import LOGIN_REQUIRED
            if LOGIN_REQUIRED and not session.get('logged_in'):
                return redirect(url_for('login'))
        except ImportError:
            # 如果配置文件中没有LOGIN_REQUIRED，默认不要求登录
            pass
        return f(*args, **kwargs)
    return decorated_function

# 添加配置重载功能
def reload_config():
    """重新加载配置文件"""
    try:
        # 清除已导入的config模块
        if 'config' in sys.modules:
            del sys.modules['config']
        
        # 重新导入config模块
        import config
        
        # 重新导入配置变量
        global WEB_HOST, WEB_PORT
        from config import WEB_HOST, WEB_PORT
        
        logger.info(f"配置文件重新加载成功: WEB_HOST={WEB_HOST}, WEB_PORT={WEB_PORT}")
        return True
    except Exception as e:
        logger.error(f"重新加载配置文件失败: {e}")
        return False

def update_config_value(key, value):
    """更新配置文件中的特定值"""
    try:
        config_file = 'config.py'
        
        # 读取当前配置文件
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式查找并替换配置项
        import re
        
        if isinstance(value, bool):
            pattern = rf'^{key}\s*=\s*.*$'
            replacement = f'{key} = {value}'
        elif isinstance(value, str):
            pattern = rf'^{key}\s*=\s*.*$'
            replacement = f'{key} = "{value}"'
        elif isinstance(value, (int, float)):
            pattern = rf'^{key}\s*=\s*.*$'
            replacement = f'{key} = {value}'
        elif isinstance(value, dict):
            # 处理字典类型
            dict_str = '{\n'
            for k, v in value.items():
                if isinstance(v, str):
                    dict_str += f"    '{k}': '{v}',\n"
                else:
                    dict_str += f"    '{k}': {v},\n"
            dict_str += '}'
            pattern = rf'^{key}\s*=\s*{{[\s\S]*?^}}'
            replacement = f'{key} = {dict_str}'
        else:
            pattern = rf'^{key}\s*=\s*.*$'
            replacement = f'{key} = {repr(value)}'
        
        # 添加调试日志
        logger.debug(f"查找配置项: {key}")
        logger.debug(f"使用模式: {pattern}")
        logger.debug(f"替换为: {replacement}")
        
        # 使用多行模式匹配
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        if new_content == content:
            # 尝试使用简单的字符串替换
            lines = content.split('\n')
            updated = False
            for i, line in enumerate(lines):
                if line.strip().startswith(f'{key} ='):
                    if isinstance(value, bool):
                        lines[i] = f'{key} = {value}'
                    elif isinstance(value, str):
                        lines[i] = f'{key} = "{value}"'
                    elif isinstance(value, (int, float)):
                        lines[i] = f'{key} = {value}'
                    else:
                        lines[i] = f'{key} = {repr(value)}'
                    updated = True
                    logger.debug(f"使用简单替换更新配置项 {key} 在第 {i+1} 行")
                    break
            
            if updated:
                new_content = '\n'.join(lines)
            else:
                logger.warning(f"未找到配置项 {key}")
                # 输出配置文件的相关行用于调试
                for i, line in enumerate(lines):
                    if key in line:
                        logger.debug(f"找到包含 {key} 的行 {i+1}: {line}")
                return False
        
        # 验证更新后的配置是否有语法错误
        try:
            compile(new_content, config_file, 'exec')
        except SyntaxError as e:
            logger.error(f"配置更新后产生语法错误: {e}")
            return False
        
        # 写回配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        logger.info(f"配置项 {key} 已更新为 {value}")
        return True
    except Exception as e:
        logger.error(f"更新配置项 {key} 失败: {e}")
        return False

def update_auto_monitor_config(enabled, interval, auto_start_enabled):
    """更新自动监控相关配置"""
    try:
        logger.info(f"开始更新自动监控配置: enabled={enabled}, interval={interval}, auto_start_enabled={auto_start_enabled}")
        
        # 更新各个配置项
        success = True
        
        # 更新AUTO_MONITOR_BUTTON_ENABLED
        logger.debug("更新AUTO_MONITOR_BUTTON_ENABLED...")
        success &= update_config_value('AUTO_MONITOR_BUTTON_ENABLED', enabled)
        
        # 更新AUTO_MONITOR_INTERVAL_VALUE
        logger.debug("更新AUTO_MONITOR_INTERVAL_VALUE...")
        success &= update_config_value('AUTO_MONITOR_INTERVAL_VALUE', interval)
        
        # 更新AUTO_START_VM_BUTTON_ENABLED
        logger.debug("更新AUTO_START_VM_BUTTON_ENABLED...")
        success &= update_config_value('AUTO_START_VM_BUTTON_ENABLED', auto_start_enabled)
        
        if success:
            # 重新加载配置
            logger.debug("重新加载配置...")
            reload_config()
            logger.info("自动监控配置更新并重新加载成功")
            return True
        else:
            logger.error("部分配置项更新失败")
            return False
    except Exception as e:
        logger.error(f"更新自动监控配置失败: {e}")
        return False

def update_web_refresh_config(enabled, interval):
    """更新Web自动刷新配置"""
    try:
        # 更新启用状态
        success1 = update_config_value('AUTO_REFRESH_BUTTON_ENABLED', enabled)
        # 更新间隔
        success2 = update_config_value('AUTO_REFRESH_INTERVAL_VALUE', interval)
        
        if success1 and success2:
            logger.info(f"Web自动刷新配置已更新: 启用={enabled}, 间隔={interval}秒")
            return True
        else:
            logger.error(f"Web自动刷新配置更新失败: 启用状态={success1}, 间隔={success2}")
        return False
    except Exception as e:
        logger.error(f"更新Web自动刷新配置失败: {e}")
        return False

# 配置Flask应用
app = Flask(__name__)
try:
    from config import SESSION_SECRET_KEY, SESSION_TIMEOUT
    app.config['SECRET_KEY'] = SESSION_SECRET_KEY
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=SESSION_TIMEOUT)
except ImportError:
    app.config['SECRET_KEY'] = 'vbox_monitor_secret_key'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# 导入配置文件
try:
    from config import *
    logger = logging.getLogger(__name__)
    logger.info(f"从配置文件加载设置: WEB_HOST={WEB_HOST}, WEB_PORT={WEB_PORT}")
except ImportError:
    # 如果配置文件不存在，使用默认配置
    WEB_PORT = 5000
    WEB_HOST = "0.0.0.0"
    LOG_LEVEL = "INFO"
    WEB_LOG_FILE = "vbox_web.log"
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
    LOG_ENCODING = "utf-8"
    VERBOSE_LOGGING = True
    logger = logging.getLogger(__name__)
    logger.warning("配置文件不存在，使用默认配置")

# 配置日志
log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(WEB_LOG_FILE, encoding=LOG_ENCODING),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 设置详细调试日志
if VERBOSE_LOGGING:
    logger.setLevel(logging.DEBUG)
    logger.debug("启用Web应用详细调试日志")

# 全局变量
monitor = None
monitoring_status = False
auto_refresh_enabled = False
auto_refresh_interval = 30
auto_refresh_thread = None

def start_auto_refresh(interval):
    """启动自动刷新"""
    global auto_refresh_thread, auto_refresh_enabled, auto_refresh_interval
    
    # 如果已有线程在运行，先停止
    if auto_refresh_thread and auto_refresh_thread.is_alive():
        stop_auto_refresh()
    
    auto_refresh_enabled = True
    auto_refresh_interval = interval
    
    def auto_refresh_task():
        logger.info(f"自动刷新任务已启动，间隔: {interval}秒")
        logger.info(f"自动刷新状态: 已开启，执行间隔: {interval}秒")
        
        while auto_refresh_enabled:
            try:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"[{current_time}] 执行自动刷新...")
                logger.info(f"自动刷新状态: 正在执行，间隔: {interval}秒")
                
                # 执行实际的刷新操作
                if monitor:
                    try:
                        # 重新扫描虚拟机
                        vm_list = monitor.get_all_vm_status()
                        logger.info(f"自动刷新完成，扫描到 {len(vm_list)} 个虚拟机")
                        
                        # 记录每个虚拟机的状态
                        for vm in vm_list:
                            logger.debug(f"虚拟机: {vm['name']}, 状态: {vm['status']}")
                        
                    except Exception as e:
                        logger.error(f"自动刷新扫描虚拟机失败: {e}")
                else:
                    logger.warning("监控器未初始化，跳过自动刷新")
                
                time.sleep(interval)
            except Exception as e:
                logger.error(f"自动刷新任务出错: {e}")
                time.sleep(interval)
    
    auto_refresh_thread = threading.Thread(target=auto_refresh_task, daemon=True)
    auto_refresh_thread.start()
    logger.info("自动刷新线程已启动")

def stop_auto_refresh():
    """停止自动刷新"""
    global auto_refresh_enabled, auto_refresh_thread
    
    auto_refresh_enabled = False
    if auto_refresh_thread and auto_refresh_thread.is_alive():
        auto_refresh_thread.join(timeout=5)
        logger.info("自动刷新线程已停止")
        logger.info("自动刷新状态: 已关闭")

def init_monitor():
    """初始化监控器"""
    global monitor, auto_refresh_enabled, auto_refresh_interval
    try:
        monitor = get_vbox_monitor()
        logger.info("VirtualBox监控器初始化成功")
        
        # 加载保存的自动刷新配置
        try:
            from config import AUTO_REFRESH_BUTTON_ENABLED, AUTO_REFRESH_INTERVAL_VALUE
            auto_refresh_enabled = AUTO_REFRESH_BUTTON_ENABLED
            auto_refresh_interval = AUTO_REFRESH_INTERVAL_VALUE
            
            if auto_refresh_enabled:
                logger.info(f"加载保存的自动刷新配置: 已启用，间隔: {auto_refresh_interval}秒")
                start_auto_refresh(auto_refresh_interval)
            else:
                logger.info("加载保存的自动刷新配置: 已禁用")
        except ImportError:
            logger.warning("无法加载自动刷新配置，使用默认值")
        
        return True
    except Exception as e:
        logger.error(f"初始化监控器失败: {e}")
        return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        try:
            from config import LOGIN_USERNAME, LOGIN_PASSWORD
            username = request.form.get('username')
            password = request.form.get('password')
            
            if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
                session['logged_in'] = True
                session['username'] = username
                session.permanent = True
                logger.info(f"用户 {username} 登录成功")
                return jsonify({
                    'success': True,
                    'message': '登录成功'
                })
            else:
                logger.warning(f"登录失败: 用户名={username}")
                return jsonify({
                    'success': False,
                    'message': '用户名或密码错误'
                })
        except ImportError:
            return jsonify({
                'success': False,
                'message': '登录配置错误'
            })
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    """退出登录"""
    session.clear()
    logger.info("用户退出登录")
    return jsonify({
        'success': True,
        'message': '退出成功'
    })

@app.route('/')
@login_required
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/vms')
@login_required
def api_get_vms():
    """获取所有虚拟机状态"""
    logger.debug("API调用: /api/vms - 获取所有虚拟机状态")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        logger.debug("调用monitor.get_all_vm_status()")
        vm_list = monitor.get_all_vm_status()
        logger.debug(f"获取到 {len(vm_list)} 个虚拟机状态")
        
        # 详细记录每个虚拟机的状态
        for vm in vm_list:
            logger.debug(f"虚拟机: {vm['name']}, 状态: {vm['status']}, UUID: {vm['uuid']}")
        
        response_data = {
            'success': True,
            'data': vm_list,
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取虚拟机列表失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机列表失败: {str(e)}'
        })

@app.route('/api/vm/<vm_name>/start')
@login_required
def api_start_vm(vm_name):
    """启动虚拟机"""
    logger.debug(f"API调用: /api/vm/{vm_name}/start - 启动虚拟机")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        logger.debug(f"调用monitor.start_vm({vm_name})")
        success = monitor.start_vm(vm_name)
        logger.debug(f"启动虚拟机 {vm_name} 结果: {success}")
        
        response_data = {
            'success': success,
            'message': f'虚拟机 {vm_name} {"启动成功" if success else "启动失败"}',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"启动虚拟机 {vm_name} 失败: {e}")
        return jsonify({
            'success': False,
            'message': f'启动虚拟机失败: {str(e)}'
        })

@app.route('/api/vm/<vm_name>/stop')
@login_required
def api_stop_vm(vm_name):
    """停止虚拟机"""
    try:
        if not monitor:
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        success = monitor.stop_vm(vm_name)
        return jsonify({
            'success': success,
            'message': f'虚拟机 {vm_name} {"停止成功" if success else "停止失败"}',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"停止虚拟机 {vm_name} 失败: {e}")
        return jsonify({
            'success': False,
            'message': f'停止虚拟机失败: {str(e)}'
        })

@app.route('/api/vm/<vm_name>/info')
@login_required
def api_get_vm_info(vm_name):
    """获取虚拟机详细信息"""
    try:
        if not monitor:
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        info = monitor.get_vm_info(vm_name)
        if info:
            return jsonify({
                'success': True,
                'data': info,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': f'获取虚拟机 {vm_name} 信息失败'
            })
    except Exception as e:
        logger.error(f"获取虚拟机 {vm_name} 信息失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机信息失败: {str(e)}'
        })

@app.route('/api/vm/<vm_name>/restart', methods=['POST'])
@login_required
def api_restart_vm(vm_name):
    """强制重启虚拟机"""
    logger.debug(f"API调用: /api/vm/{vm_name}/restart - 强制重启虚拟机")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        logger.debug(f"调用monitor.restart_vm({vm_name})")
        success = monitor.restart_vm(vm_name)
        logger.debug(f"强制重启虚拟机 {vm_name} 结果: {success}")
        
        response_data = {
            'success': success,
            'message': f'虚拟机 {vm_name} {"强制重启成功" if success else "强制重启失败"}',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"强制重启虚拟机 {vm_name} 失败: {e}")
        return jsonify({
            'success': False,
            'message': f'强制重启虚拟机失败: {str(e)}'
        })







@app.route('/api/monitor/start')
@login_required
def api_start_monitoring():
    """开始监控"""
    global monitoring_status
    try:
        if not monitor:
            logger.warning("监控器未初始化，无法启动监控")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        interval = request.args.get('interval', 30, type=int)
        auto_start = request.args.get('auto_start', 'true').lower() == 'true'
        start_time = request.args.get('start_time', None)
        
        logger.info(f"启动监控: 间隔={interval}秒, 自动启动={auto_start}")
        logger.debug(f"监控启动请求参数: interval={interval}, auto_start={auto_start}, start_time={start_time}")
        
        # 记录启动时间
        if start_time:
            logger.info(f"监控启动时间: {start_time}")
        
        monitor.start_monitoring(interval, auto_start, start_time)
        monitoring_status = True
        
        auto_start_text = "启用" if auto_start else "禁用"
        logger.info(f"自动监控启动成功: 间隔={interval}秒, 自动启动={auto_start_text}")
        logger.info(f"自动监控状态: 已开启，执行间隔: {interval}秒")
        
        return jsonify({
            'success': True,
            'message': f'开始监控，间隔: {interval}秒，自动启动: {auto_start_text}',
            'timestamp': datetime.now().isoformat(),
            'start_time': start_time
        })
    except Exception as e:
        logger.error(f"开始监控失败: {e}")
        return jsonify({
            'success': False,
            'message': f'开始监控失败: {str(e)}'
        })

@app.route('/api/monitor/stop')
@login_required
def api_stop_monitoring():
    """停止监控"""
    global monitoring_status
    try:
        if not monitor:
            logger.warning("监控器未初始化，无法停止监控")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        logger.info("收到停止监控请求")
        logger.debug("停止监控操作开始")
        
        monitor.stop_monitoring()
        monitoring_status = False
        
        logger.info("自动监控停止成功")
        logger.info("自动监控状态: 已关闭")
        logger.debug("监控状态已更新为停止")
        
        return jsonify({
            'success': True,
            'message': '停止监控',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"停止监控失败: {e}")
        return jsonify({
            'success': False,
            'message': f'停止监控失败: {str(e)}'
        })

@app.route('/api/monitor/status')
@login_required
def api_get_monitor_status():
    """获取监控状态"""
    try:
        if not monitor:
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        return jsonify({
            'success': True,
            'data': {
                'monitoring': monitoring_status,
                'vbox_dir': monitor.vbox_dir,
                'vboxmanage_path': monitor.vboxmanage_path,
                'vm_count': len(monitor.vms)
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取监控状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取监控状态失败: {str(e)}'
        })

@app.route('/api/auto_start')
@login_required
def api_auto_start_stopped_vms():
    """手动执行自动启动"""
    try:
        if not monitor:
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        results = monitor.auto_start_stopped_vms()
        return jsonify({
            'success': True,
            'data': results,
            'message': f'自动启动完成，处理了 {len(results)} 个虚拟机',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"自动启动失败: {e}")
        return jsonify({
            'success': False,
            'message': f'自动启动失败: {str(e)}'
        })

@app.route('/api/scan')
@login_required
def api_scan_vms():
    """重新扫描虚拟机"""
    try:
        if not monitor:
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        vms = monitor.scan_vms()
        return jsonify({
            'success': True,
            'data': vms,
            'message': f'扫描完成，发现 {len(vms)} 个虚拟机',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"扫描虚拟机失败: {e}")
        return jsonify({
            'success': False,
            'message': f'扫描虚拟机失败: {str(e)}'
        })

@app.route('/api/monitor/vm_status')
def api_monitor_vm_status():
    """监控虚拟机状态"""
    logger.debug("API调用: /api/monitor/vm_status - 监控虚拟机状态")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        logger.debug("调用monitor.monitor_vm_status()")
        result = monitor.monitor_vm_status()
        logger.debug(f"监控虚拟机状态结果: {result}")
        
        response_data = {
            'success': True,
            'data': result,
            'message': f'监控完成，总计{result["total_vms"]}个虚拟机',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"监控虚拟机状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'监控虚拟机状态失败: {str(e)}'
        })

@app.route('/api/config/update_directories', methods=['POST'])
def api_update_directories():
    """更新选中的虚拟机目录"""
    logger.debug("API调用: /api/config/update_directories - 更新选中目录")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        # 获取请求数据
        data = request.get_json()
        if not data or 'directories' not in data:
            return jsonify({
                'success': False,
                'message': '缺少directories参数'
            })
        
        directories = data['directories']
        logger.debug(f"更新选中目录: {directories}")
        
        success = monitor.update_selected_directories(directories)
        
        response_data = {
            'success': success,
            'message': f'更新选中目录{"成功" if success else "失败"}',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"更新选中目录失败: {e}")
        return jsonify({
            'success': False,
            'message': f'更新选中目录失败: {str(e)}'
        })

@app.route('/api/config/get_directories')
def api_get_directories():
    """获取当前选中的虚拟机目录"""
    logger.debug("API调用: /api/config/get_directories - 获取选中目录")
    try:
        # 安全地导入配置
        from config import SELECTED_VM_DIRECTORIES
    except ImportError as e:
        logger.error(f"导入SELECTED_VM_DIRECTORIES失败: {e}")
        # 如果导入失败，使用默认值
        SELECTED_VM_DIRECTORIES = [r"D:\Users\wx\VirtualBox VMs"]
        
        response_data = {
            'success': True,
            'data': SELECTED_VM_DIRECTORIES,
            'message': f'获取到 {len(SELECTED_VM_DIRECTORIES)} 个选中目录',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取选中目录失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取选中目录失败: {str(e)}'
        })

@app.route('/api/vm/<vm_name>/clear_failure', methods=['POST'])
def api_clear_start_failure(vm_name):
    """清除虚拟机启动失败标记"""
    logger.debug(f"API调用: /api/vm/{vm_name}/clear_failure - 清除启动失败标记")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        monitor.clear_start_failure(vm_name)
        
        response_data = {
            'success': True,
            'message': f'已清除虚拟机 {vm_name} 的启动失败标记',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"清除启动失败标记失败: {e}")
        return jsonify({
            'success': False,
            'message': f'清除启动失败标记失败: {str(e)}'
        })

@app.route('/api/vm/clear_all_failures', methods=['POST'])
def api_clear_all_start_failures():
    """清除所有虚拟机启动失败标记"""
    logger.debug("API调用: /api/vm/clear_all_failures - 清除所有启动失败标记")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        start_failures = monitor.get_start_failures()
        cleared_count = len(start_failures)
        
        # 清除所有失败标记
        for vm_name in list(start_failures.keys()):
            monitor.clear_start_failure(vm_name)
        
        response_data = {
            'success': True,
            'message': f'已清除 {cleared_count} 个虚拟机的启动失败标记',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"清除所有启动失败标记失败: {e}")
        return jsonify({
            'success': False,
            'message': f'清除所有启动失败标记失败: {str(e)}'
        })

@app.route('/api/scan_directory', methods=['POST'])
def api_scan_directory():
    """扫描目录中的虚拟机文件"""
    logger.debug("API调用: /api/scan_directory - 扫描目录")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        data = request.get_json()
        if not data or 'directory' not in data:
            return jsonify({
                'success': False,
                'message': '缺少directory参数'
            })
        
        directory = data['directory']
        logger.debug(f"扫描目录: {directory}")
        
        scan_result = monitor.scan_directory_for_vms(directory)
        
        response_data = {
            'success': scan_result['success'],
            'data': scan_result,
            'message': scan_result['message'],
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"扫描目录失败: {e}")
        return jsonify({
            'success': False,
            'message': f'扫描目录失败: {str(e)}'
        })

@app.route('/api/config/vbox_dir')
def api_get_vbox_dir():
    """获取VBOX_DIR配置"""
    logger.debug("API调用: /api/config/vbox_dir - 获取VBOX_DIR配置")
    try:
        from config import VBOX_DIR
        
        response_data = {
            'success': True,
            'data': {
                'vbox_dir': VBOX_DIR
            },
            'message': '获取VBOX_DIR配置成功',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取VBOX_DIR配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取VBOX_DIR配置失败: {str(e)}'
        })

@app.route('/api/vm/<vm_name>/exception')
def api_get_vm_exception(vm_name):
    """获取指定虚拟机的异常状态"""
    logger.debug(f"API调用: /api/vm/{vm_name}/exception - 获取虚拟机异常状态")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        exception_status = monitor.get_vm_exception_status(vm_name)
        
        response_data = {
            'success': True,
            'data': exception_status,
            'message': '获取虚拟机异常状态成功' if exception_status else '虚拟机无异常状态',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取虚拟机异常状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机异常状态失败: {str(e)}'
        })

@app.route('/api/vm/<vm_name>/clear_exception', methods=['POST'])
def api_clear_vm_exception(vm_name):
    """清除指定虚拟机的异常状态"""
    logger.debug(f"API调用: /api/vm/{vm_name}/clear_exception - 清除虚拟机异常状态")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        monitor.clear_vm_exception(vm_name)
        
        response_data = {
            'success': True,
            'message': f'已清除虚拟机 {vm_name} 的异常状态',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"清除虚拟机异常状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'清除虚拟机异常状态失败: {str(e)}'
        })

@app.route('/api/vm/exceptions')
def api_get_all_exceptions():
    """获取所有虚拟机的异常状态"""
    logger.debug("API调用: /api/vm/exceptions - 获取所有虚拟机异常状态")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        exceptions = monitor.get_vm_exceptions()
        
        response_data = {
            'success': True,
            'data': exceptions,
            'message': f'获取异常状态成功，共 {len(exceptions)} 个虚拟机有异常',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取所有虚拟机异常状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取所有虚拟机异常状态失败: {str(e)}'
        })

@app.route('/api/config/auto_monitor')
@login_required
def api_get_auto_monitor_config():
    """获取自动监控配置"""
    logger.debug("API调用: /api/config/auto_monitor - 获取自动监控配置")
    try:
        # 安全地导入配置
        from config import (
            AUTO_MONITOR_BUTTON_ENABLED,
            AUTO_MONITOR_INTERVAL_VALUE,
            AUTO_START_VM_BUTTON_ENABLED
        )
        
        # 打印调试信息
        logger.info("=== 自动监控配置调试信息 ===")
        logger.info(f"AUTO_MONITOR_BUTTON_ENABLED: {AUTO_MONITOR_BUTTON_ENABLED}")
        logger.info(f"AUTO_MONITOR_INTERVAL_VALUE: {AUTO_MONITOR_INTERVAL_VALUE}")
        logger.info(f"AUTO_START_VM_BUTTON_ENABLED: {AUTO_START_VM_BUTTON_ENABLED}")
        logger.info("================================")
        
        response_data = {
            'success': True,
            'data': {
                'button_enabled': AUTO_MONITOR_BUTTON_ENABLED,
                'interval_value': AUTO_MONITOR_INTERVAL_VALUE,
                'auto_start_button_enabled': AUTO_START_VM_BUTTON_ENABLED
            },
            'message': '获取自动监控配置成功',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
        
    except ImportError as e:
        logger.error(f"导入自动监控配置失败: {e}")
        # 如果导入失败，使用默认值
        AUTO_MONITOR_BUTTON_ENABLED = False
        AUTO_MONITOR_INTERVAL_VALUE = 30
        AUTO_START_VM_BUTTON_ENABLED = False
        
        response_data = {
            'success': True,
            'data': {
                'button_enabled': AUTO_MONITOR_BUTTON_ENABLED,
                'interval_value': AUTO_MONITOR_INTERVAL_VALUE,
                'auto_start_button_enabled': AUTO_START_VM_BUTTON_ENABLED
            },
            'message': '获取自动监控配置成功',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取自动监控配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取自动监控配置失败: {str(e)}'
        })

@app.route('/api/config/auto_monitor', methods=['POST'])
@login_required
def api_save_auto_monitor_config():
    """保存自动监控配置"""
    logger.debug("API调用: /api/config/auto_monitor - 保存自动监控配置")
    try:
        data = request.get_json()
        if not data:
            logger.warning("缺少配置数据")
            return jsonify({
                'success': False,
                'message': '缺少配置数据'
            })
        
        logger.info(f"收到配置更新请求: {data}")
        
        # 验证配置参数
        enabled = data.get('enabled', True)
        interval = data.get('interval', 30)
        auto_start_enabled = data.get('auto_start_enabled', True)
        
        logger.debug(f"配置参数: enabled={enabled}, interval={interval}, auto_start_enabled={auto_start_enabled}")
        
        # 使用新的配置更新机制
        if update_auto_monitor_config(enabled, interval, auto_start_enabled):
            # 如果监控正在运行且配置发生变化，重新启动监控
            if monitor and hasattr(monitor, 'monitoring') and monitor.monitoring:
                logger.info("监控正在运行，将重新启动以应用新配置")
                monitor.stop_monitoring()
                time.sleep(1)  # 等待停止完成
                if enabled:
                    # 记录新的启动时间
                    start_time = datetime.now().isoformat()
                    monitor.start_monitoring(interval, auto_start_enabled, start_time)
                    logger.info(f"自动监控已重新启动: 间隔={interval}秒, 自动启动={auto_start_enabled}, 启动时间={start_time}")
                    logger.info(f"自动监控状态: 已开启，执行间隔: {interval}秒")
                else:
                    logger.info("自动监控状态: 已关闭")
            elif enabled:
                # 如果监控未运行但配置为启用，启动监控
                start_time = datetime.now().isoformat()
                monitor.start_monitoring(interval, auto_start_enabled, start_time)
                logger.info(f"自动监控已启动: 间隔={interval}秒, 自动启动={auto_start_enabled}, 启动时间={start_time}")
                logger.info(f"自动监控状态: 已开启，执行间隔: {interval}秒")
            else:
                logger.info("自动监控状态: 已关闭")
            
            response_data = {
                'success': True,
                'message': '自动监控配置保存并立即生效',
                'timestamp': datetime.now().isoformat()
            }
            logger.debug(f"返回响应: {response_data}")
            return jsonify(response_data)
        else:
            return jsonify({
                'success': False,
                'message': '配置更新失败'
            })
    except Exception as e:
        logger.error(f"保存自动监控配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'保存自动监控配置失败: {str(e)}'
        })

@app.route('/api/config/web_refresh')
@login_required
def api_get_web_refresh_config():
    """获取Web自动刷新配置"""
    logger.debug("API调用: /api/config/web_refresh - 获取Web自动刷新配置")
    try:
        # 安全地导入配置
        try:
            from config import (
                AUTO_REFRESH_BUTTON_ENABLED,
                AUTO_REFRESH_INTERVAL_VALUE
            )
            
            # 打印调试信息
            logger.info("=== Web自动刷新配置调试信息 ===")
            logger.info(f"AUTO_REFRESH_BUTTON_ENABLED: {AUTO_REFRESH_BUTTON_ENABLED}")
            logger.info(f"AUTO_REFRESH_INTERVAL_VALUE: {AUTO_REFRESH_INTERVAL_VALUE}")
            logger.info("=====================================")
            
        except ImportError as e:
            logger.error(f"导入Web自动刷新配置失败: {e}")
            # 如果导入失败，使用默认值
            AUTO_REFRESH_BUTTON_ENABLED = False
            AUTO_REFRESH_INTERVAL_VALUE = 30
            
            logger.info("=== 使用默认值 ===")
            logger.info(f"AUTO_REFRESH_BUTTON_ENABLED: {AUTO_REFRESH_BUTTON_ENABLED}")
            logger.info(f"AUTO_REFRESH_INTERVAL_VALUE: {AUTO_REFRESH_INTERVAL_VALUE}")
            logger.info("==================")
        
        response_data = {
            'success': True,
            'data': {
                'default_interval': AUTO_REFRESH_INTERVAL_VALUE,
                'web_auto_refresh_enabled': AUTO_REFRESH_BUTTON_ENABLED,
                'button_enabled': AUTO_REFRESH_BUTTON_ENABLED,
                'interval_value': AUTO_REFRESH_INTERVAL_VALUE
            },
            'message': '获取Web自动刷新配置成功',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取Web自动刷新配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取Web自动刷新配置失败: {str(e)}'
        })

@app.route('/api/config/web_refresh', methods=['POST'])
@login_required
def api_update_web_refresh_interval():
    """更新Web自动刷新配置"""
    logger.debug("API调用: /api/config/web_refresh - 更新Web自动刷新配置")
    try:
        data = request.get_json()
        if not data:
            logger.warning("缺少配置数据")
            return jsonify({
                'success': False,
                'message': '缺少配置数据'
            })
        
        enabled = data.get('enabled', False)
        interval = data.get('interval', 30)
        logger.info(f"收到Web自动刷新配置更新请求: 启用={enabled}, 间隔={interval}秒")
        
        # 直接更新配置文件中的AUTO_REFRESH_BUTTON_ENABLED
        success1 = update_config_value('AUTO_REFRESH_BUTTON_ENABLED', enabled)
        
        # 直接更新配置文件中的AUTO_REFRESH_INTERVAL_VALUE
        success2 = update_config_value('AUTO_REFRESH_INTERVAL_VALUE', interval)
        
        if success1 and success2:
            # 更新全局自动刷新状态
            global auto_refresh_enabled, auto_refresh_interval
            auto_refresh_enabled = enabled
            auto_refresh_interval = interval
            
            if enabled:
                logger.info(f"Web自动刷新已启用，间隔: {interval}秒")
                logger.info(f"自动刷新状态: 已开启，执行间隔: {interval}秒")
                # 启动自动刷新
                start_auto_refresh(interval)
                status_message = f"自动刷新已启用，间隔: {interval}秒"
            else:
                logger.info("Web自动刷新已禁用")
                logger.info("自动刷新状态: 已关闭")
                # 停止自动刷新
                stop_auto_refresh()
                status_message = "自动刷新已禁用"
            
            response_data = {
                'success': True,
                'message': status_message,
                'data': {
                    'enabled': enabled,
                    'interval': interval,
                    'status': status_message
                },
                'timestamp': datetime.now().isoformat()
            }
            logger.debug(f"返回响应: {response_data}")
            return jsonify(response_data)
        else:
            return jsonify({
                'success': False,
                'message': 'Web自动刷新配置更新失败'
            })
    except Exception as e:
        logger.error(f"更新Web自动刷新配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'更新Web自动刷新配置失败: {str(e)}'
        })

@app.route('/api/config/auto_refresh/status')
def api_get_auto_refresh_status():
    """获取自动刷新状态"""
    logger.debug("API调用: /api/config/auto_refresh/status - 获取自动刷新状态")
    try:
        return jsonify({
            'success': True,
            'data': {
                'enabled': auto_refresh_enabled,
                'interval': auto_refresh_interval,
                'thread_alive': auto_refresh_thread.is_alive() if auto_refresh_thread else False
            },
            'message': '获取自动刷新状态成功',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取自动刷新状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取自动刷新状态失败: {str(e)}'
        })

@app.route('/api/config/web_server')
def api_get_web_server_config():
    """获取Web服务器配置"""
    logger.debug("API调用: /api/config/web_server - 获取Web服务器配置")
    try:
        return jsonify({
            'success': True,
            'data': {
                'host': WEB_HOST,
                'port': WEB_PORT,
                'url': f"http://{WEB_HOST}:{WEB_PORT}"
            },
            'message': '获取Web服务器配置成功',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取Web服务器配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取Web服务器配置失败: {str(e)}'
        })

@app.route('/api/config/web_server', methods=['POST'])
def api_update_web_server_config():
    """更新Web服务器配置"""
    logger.debug("API调用: /api/config/web_server - 更新Web服务器配置")
    try:
        data = request.get_json()
        if not data:
            logger.warning("缺少配置数据")
            return jsonify({
                'success': False,
                'message': '缺少配置数据'
            })
        
        new_host = data.get('host', WEB_HOST)
        new_port = data.get('port', WEB_PORT)
        
        logger.info(f"收到Web服务器配置更新请求: host={new_host}, port={new_port}")
        
        # 更新配置文件
        success1 = update_config_value('WEB_HOST', new_host)
        success2 = update_config_value('WEB_PORT', new_port)
        
        if success1 and success2:
            # 重新加载配置
            reload_config()
            
            logger.info(f"Web服务器配置已更新: host={new_host}, port={new_port}")
            logger.warning("端口配置已更新，需要重启Web服务才能生效")
            
            response_data = {
                'success': True,
                'message': f'Web服务器配置已更新: {new_host}:{new_port}，需要重启服务生效',
                'data': {
                    'host': new_host,
                    'port': new_port,
                    'url': f"http://{new_host}:{new_port}"
                },
                'timestamp': datetime.now().isoformat()
            }
            logger.debug(f"返回响应: {response_data}")
            return jsonify(response_data)
        else:
            return jsonify({
                'success': False,
                'message': 'Web服务器配置更新失败'
            })
    except Exception as e:
        logger.error(f"更新Web服务器配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'更新Web服务器配置失败: {str(e)}'
        })

@app.route('/api/config/update_parameter', methods=['POST'])
@login_required
def api_update_config_parameter():
    """更新单个配置参数"""
    logger.debug("API调用: /api/config/update_parameter - 更新配置参数")
    try:
        data = request.get_json()
        if not data:
            logger.warning("缺少配置数据")
            return jsonify({
                'success': False,
                'message': '缺少配置数据'
            })
        
        parameter_name = data.get('parameter')
        value = data.get('value')
        
        if parameter_name is None or value is None:
            logger.warning("缺少参数名或值")
            return jsonify({
                'success': False,
                'message': '缺少参数名或值'
            })
        
        logger.info(f"收到配置参数更新请求: {parameter_name} = {value}")
        
        # 使用update_config_value函数更新配置文件
        if update_config_value(parameter_name, value):
            logger.info(f"配置参数 {parameter_name} 更新成功")
            response_data = {
                'success': True,
                'message': f'配置参数 {parameter_name} 更新成功',
                'data': {
                    'parameter': parameter_name,
                    'value': value
                },
                'timestamp': datetime.now().isoformat()
            }
            logger.debug(f"返回响应: {response_data}")
            return jsonify(response_data)
        else:
            logger.error(f"配置参数 {parameter_name} 更新失败")
            return jsonify({
                'success': False,
                'message': f'配置参数 {parameter_name} 更新失败'
            })
    except Exception as e:
        logger.error(f"更新配置参数失败: {e}")
        return jsonify({
            'success': False,
            'message': f'更新配置参数失败: {str(e)}'
        })

@app.route('/api/monitor/last_results')
def api_get_last_monitor_results():
    """获取最近一次监控执行结果"""
    logger.debug("API调用: /api/monitor/last_results - 获取最近监控结果")
    try:
        if not monitor:
            logger.warning("监控器未初始化")
            return jsonify({
                'success': False,
                'message': '监控器未初始化'
            })
        
        # 获取监控器的最后执行结果
        last_results = getattr(monitor, 'last_monitor_results', [])
        monitoring_status = getattr(monitor, 'monitoring', False)
        auto_start_enabled = getattr(monitor, 'auto_start_enabled', False)
        
        logger.debug(f"监控状态: monitoring={monitoring_status}, auto_start_enabled={auto_start_enabled}")
        logger.debug(f"最近监控结果数量: {len(last_results)}")
        
        if last_results:
            success_count = sum(1 for r in last_results if r['success'])
            logger.info(f"最近监控结果: 总数={len(last_results)}, 成功={success_count}")
        
        response_data = {
            'success': True,
            'data': {
                'last_results': last_results,
                'monitoring': monitoring_status,
                'auto_start_enabled': auto_start_enabled,
                'timestamp': datetime.now().isoformat()
            },
            'message': f'获取监控结果成功，共 {len(last_results)} 个操作',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取监控结果失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取监控结果失败: {str(e)}'
        })

@app.route('/api/logs/monitor')
def api_get_monitor_logs():
    """获取监控日志"""
    logger.debug("API调用: /api/logs/monitor - 获取监控日志")
    try:
        from config import MONITOR_LOG_FILE
        
        logs = []
        if os.path.exists(MONITOR_LOG_FILE):
            try:
                with open(MONITOR_LOG_FILE, 'r', encoding='utf-8') as f:
                    # 读取最后100行日志
                    lines = f.readlines()
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                    
                    for line in recent_lines:
                        line = line.strip()
                        if line:
                            # 解析日志级别
                            level = 'info'
                            if 'DEBUG' in line:
                                level = 'debug'
                            elif 'INFO' in line:
                                level = 'info'
                            elif 'WARNING' in line:
                                level = 'warning'
                            elif 'ERROR' in line:
                                level = 'error'
                            elif 'CRITICAL' in line:
                                level = 'critical'
                            
                            logs.append({
                                'message': line,
                                'level': level,
                                'timestamp': datetime.now().isoformat()
                            })
            except Exception as e:
                logger.error(f"读取监控日志文件失败: {e}")
                logs.append({
                    'message': f'读取日志文件失败: {str(e)}',
                    'level': 'error',
                    'timestamp': datetime.now().isoformat()
                })
        else:
            logs.append({
                'message': '监控日志文件不存在',
                'level': 'warning',
                'timestamp': datetime.now().isoformat()
            })
        
        response_data = {
            'success': True,
            'data': {
                'logs': logs,
                'total_lines': len(logs),
                'timestamp': datetime.now().isoformat()
            },
            'message': f'获取监控日志成功，共 {len(logs)} 行',
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"返回响应: 日志行数={len(logs)}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取监控日志失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取监控日志失败: {str(e)}'
        })

# 在模块导入时初始化监控器
if not init_monitor():
    print("初始化监控器失败，请检查VirtualBox是否正确安装")
    sys.exit(1)

if __name__ == '__main__':
    print("VirtualBox监控Web应用启动中...")
    print(f"配置文件端口: {WEB_PORT}")
    print(f"配置文件主机: {WEB_HOST}")
    print(f"访问地址: http://{WEB_HOST}:{WEB_PORT}")
    
    # 启动Flask应用
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False) 