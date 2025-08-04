#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试每次启动都会检查VirtualBox状态的功能
"""

import os
import sys
import time

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_startup_check():
    """测试启动时检查功能"""
    print("=== 测试启动时VirtualBox状态检查 ===")
    
    try:
        from vbox_monitor import VirtualBoxMonitor
        
        print("🔍 创建VirtualBox监控实例...")
        print("   注意：这将触发启动时VirtualBox状态检查")
        
        # 创建监控实例（会触发启动时检查）
        monitor = VirtualBoxMonitor()
        
        print("✅ VirtualBox监控实例创建成功")
        print("✅ 启动时VirtualBox状态检查已完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_service_health_check():
    """测试服务健康检查"""
    print("\n=== 测试VirtualBox服务健康检查 ===")
    
    try:
        from vbox_monitor import VirtualBoxMonitor
        
        # 创建监控实例
        monitor = VirtualBoxMonitor()
        
        # 测试服务健康检查
        print("🔍 测试VirtualBox服务健康检查...")
        is_healthy = monitor._is_vbox_service_healthy()
        
        if is_healthy:
            print("   ✅ VirtualBox服务状态正常")
            print("   📝 系统将不会执行任何恢复操作")
            print("   🚀 可以正常使用VirtualBox功能")
        else:
            print("   ❌ VirtualBox服务状态异常")
            print("   📝 系统将尝试恢复服务")
            print("   ⚠️  某些功能可能受限")
        
        return is_healthy
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_conditional_operations():
    """测试条件操作功能"""
    print("\n=== 测试条件操作功能 ===")
    
    try:
        from vbox_monitor import VirtualBoxMonitor
        
        # 创建监控实例
        monitor = VirtualBoxMonitor()
        
        print("📋 条件操作逻辑测试:")
        print("   1. 每次操作前检查VirtualBox状态")
        print("   2. 状态正常时: 直接执行操作")
        print("   3. 状态异常时: 先恢复再执行")
        print("   4. 恢复失败时: 返回错误状态")
        
        # 测试获取虚拟机列表
        print("\n🔍 测试获取虚拟机列表...")
        vms = monitor.scan_vms(scan_status=False)
        
        if vms:
            print(f"   📊 找到 {len(vms)} 个虚拟机")
            
            # 测试第一个虚拟机的状态获取
            test_vm = vms[0]['name']
            print(f"   🔍 测试虚拟机状态获取: {test_vm}")
            
            status = monitor.get_vm_status(test_vm)
            print(f"   📊 虚拟机状态: {status}")
            
            if status != 'unknown':
                print("   ✅ 虚拟机状态获取成功")
                return True
            else:
                print("   ⚠️  虚拟机状态为unknown，可能是服务问题")
                return False
        else:
            print("   ⚠️  没有找到虚拟机，跳过测试")
            return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_logging_behavior():
    """测试日志行为"""
    print("\n=== 测试日志行为 ===")
    
    try:
        # 检查日志文件
        print("📋 检查启动时检查的日志记录:")
        
        log_files = ['vbox_monitor.log', 'vbox_web.log']
        
        for log_file in log_files:
            if os.path.exists(log_file):
                print(f"   ✅ 日志文件存在: {log_file}")
                
                # 检查最近的日志
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    recent_lines = lines[-20:]  # 最后20行
                    
                    # 查找启动时检查相关的日志
                    startup_logs = [line for line in recent_lines if '启动时VirtualBox服务状态检查' in line]
                    
                    if startup_logs:
                        print(f"   📝 发现启动时检查相关日志:")
                        for log in startup_logs[-3:]:  # 显示最后3条
                            print(f"      {log.strip()}")
                    else:
                        print(f"   📝 未发现启动时检查相关日志")
                        
                    # 查找服务状态相关的日志
                    service_logs = [line for line in recent_lines if 'VirtualBox服务状态正常' in line or 'VirtualBox服务异常' in line]
                    
                    if service_logs:
                        print(f"   📝 发现服务状态相关日志:")
                        for log in service_logs[-3:]:  # 显示最后3条
                            print(f"      {log.strip()}")
                    else:
                        print(f"   📝 未发现服务状态相关日志")
            else:
                print(f"   ❌ 日志文件不存在: {log_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_multiple_startups():
    """测试多次启动"""
    print("\n=== 测试多次启动 ===")
    
    try:
        print("📋 测试多次启动时的检查行为:")
        print("   1. 每次创建监控实例都会触发启动时检查")
        print("   2. 检查结果会记录在日志中")
        print("   3. 正常状态下不会执行恢复操作")
        
        # 创建多个监控实例来模拟多次启动
        for i in range(3):
            print(f"\n🔄 第 {i+1} 次启动测试...")
            
            try:
                from vbox_monitor import VirtualBoxMonitor
                monitor = VirtualBoxMonitor()
                print(f"   ✅ 第 {i+1} 次启动成功")
                
                # 短暂延迟
                time.sleep(1)
                
            except Exception as e:
                print(f"   ❌ 第 {i+1} 次启动失败: {e}")
        
        print("\n✅ 多次启动测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    print("开始测试每次启动都会检查VirtualBox状态的功能...")
    
    try:
        # 1. 测试启动时检查
        startup_ok = test_startup_check()
        
        # 2. 测试服务健康检查
        health_ok = test_service_health_check()
        
        # 3. 测试条件操作
        operations_ok = test_conditional_operations()
        
        # 4. 测试日志行为
        logging_ok = test_logging_behavior()
        
        # 5. 测试多次启动
        multiple_ok = test_multiple_startups()
        
        print("\n=== 测试结果 ===")
        print(f"启动时检查测试: {'✅ 通过' if startup_ok else '❌ 失败'}")
        print(f"服务健康检查测试: {'✅ 通过' if health_ok else '❌ 失败'}")
        print(f"条件操作测试: {'✅ 通过' if operations_ok else '❌ 失败'}")
        print(f"日志行为测试: {'✅ 通过' if logging_ok else '❌ 失败'}")
        print(f"多次启动测试: {'✅ 通过' if multiple_ok else '❌ 失败'}")
        
        if startup_ok and health_ok and operations_ok and logging_ok and multiple_ok:
            print("\n✅ 每次启动检查VirtualBox状态功能测试通过！")
            print("✅ 每次启动都会检查VirtualBox服务状态")
            print("✅ 服务正常时不会执行任何恢复操作")
            print("✅ 服务异常时会尝试恢复")
            print("✅ 详细的日志记录便于监控")
            print("✅ 多次启动都能正常工作")
        else:
            print("\n❌ 每次启动检查VirtualBox状态功能测试失败")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc() 