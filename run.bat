@echo off
chcp 65001 >nul
echo VirtualBox虚拟机监控系统
echo ================================
echo.

REM 检查Python是否安装
echo [1/5] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)
echo ✅ Python环境检查通过

REM 检查配置文件
echo [2/5] 检查配置文件...
python -c "import config; print('✅ 配置文件加载成功')" 2>nul
if errorlevel 1 (
    echo ❌ 错误: 配置文件存在语法错误
    echo 请检查 config.py 文件
    pause
    exit /b 1
)
echo ✅ 配置文件检查通过

REM 检查VirtualBox是否安装
echo [3/5] 检查VirtualBox安装...
python -c "from vbox_monitor import VirtualBoxMonitor; print('✅ VirtualBox检测成功')" 2>nul
if errorlevel 1 (
    echo ❌ 错误: VirtualBox未正确安装或配置
    echo 请确保VirtualBox已安装，或检查配置文件中的路径设置
    pause
    exit /b 1
)
echo ✅ VirtualBox检查通过

REM 安装依赖
echo [4/5] 检查Python依赖...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo ⚠️ 警告: 依赖安装可能有问题，但继续启动...
) else (
    echo ✅ 依赖检查完成
)

REM 创建日志目录
if not exist "log" mkdir log
echo ✅ 日志目录检查完成

REM 启动监控系统
echo [5/5] 启动VirtualBox监控系统...
echo.
echo ================================
echo 🚀 系统启动中...
echo 📊 访问地址: http://localhost:5000
echo 👤 默认登录: admin / 123456
echo 📝 日志文件: log/vbox_web_*.log
echo 🛑 按 Ctrl+C 停止服务
echo ================================
echo.

python vbox_web.py

if errorlevel 1 (
    echo.
    echo ❌ 系统启动失败，请检查错误信息
    echo 📝 查看日志文件: log/vbox_web_*.log
) else (
    echo.
    echo ✅ 系统已正常停止
)

pause 