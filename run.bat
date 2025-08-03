@echo off
chcp 65001 >nul
echo VirtualBox虚拟机监控系统
echo ================================

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

REM 检查VirtualBox是否安装
echo 检查VirtualBox安装...
python -c "from vbox_monitor import VirtualBoxMonitor; print('VirtualBox检测成功')" 2>nul
if errorlevel 1 (
    echo 错误: VirtualBox未正确安装或配置
    echo 请确保VirtualBox已安装，或检查配置文件中的路径设置
    pause
    exit /b 1
)

REM 安装依赖
echo 检查Python依赖...
pip install -r requirements.txt >nul 2>&1

REM 启动监控系统
echo 启动VirtualBox监控系统...
echo 访问地址: http://localhost:5000
echo 按 Ctrl+C 停止服务
echo.

python vbox_web.py

pause 