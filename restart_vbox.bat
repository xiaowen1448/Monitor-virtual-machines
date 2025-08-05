@echo off
chcp 65001 >nul
echo VirtualBox服务重启工具
echo ================================
echo.

echo [1/3] 正在终止VirtualBox相关进程...

taskkill /F /IM VirtualBox.exe >nul 2>&1
taskkill /F /IM VBoxSVC.exe >nul 2>&1
taskkill /F /IM VBoxHeadless.exe >nul 2>&1
taskkill /F /IM VBoxManage.exe >nul 2>&1
taskkill /F /IM VBoxNetDHCP.exe >nul 2>&1
taskkill /F /IM VBoxNetNAT.exe >nul 2>&1

echo ✅ 所有VirtualBox进程已终止
echo.

echo [2/3] 等待进程完全退出...
timeout /t 3 >nul
echo ✅ 等待完成
echo.

echo [3/3] 正在重新启动VirtualBox...

REM 检查VirtualBox安装路径
if exist "C:\Program Files\Oracle\VirtualBox\VirtualBox.exe" (
    start "" "C:\Program Files\Oracle\VirtualBox\VirtualBox.exe"
    echo ✅ VirtualBox已启动 (64位版本)
) else if exist "C:\Program Files (x86)\Oracle\VirtualBox\VirtualBox.exe" (
    start "" "C:\Program Files (x86)\Oracle\VirtualBox\VirtualBox.exe"
    echo ✅ VirtualBox已启动 (32位版本)
) else (
    echo ❌ 错误: 未找到VirtualBox安装
    echo 请确保VirtualBox已正确安装
    pause
    exit /b 1
)

echo.
echo ================================
echo 🎉 VirtualBox服务重启完成！
echo 📊 现在可以启动监控系统了
echo ================================
echo.

pause
