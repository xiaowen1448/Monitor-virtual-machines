@echo off
echo 正在杀死所有 VirtualBox 相关进程...

taskkill /F /IM VirtualBox.exe >nul 2>&1
taskkill /F /IM VBoxSVC.exe >nul 2>&1
taskkill /F /IM VBoxHeadless.exe >nul 2>&1
taskkill /F /IM VBoxManage.exe >nul 2>&1
taskkill /F /IM VBoxNetDHCP.exe >nul 2>&1
taskkill /F /IM VBoxNetNAT.exe >nul 2>&1

echo 所有进程已终止。
timeout /t 2 >nul

echo 正在重新启动 VirtualBox...
start "" "C:\Program Files\Oracle\VirtualBox\VirtualBox.exe"
echo 启动完成。
