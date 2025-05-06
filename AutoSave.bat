@echo off
title Git Auto Commit Debug

:: 切换到目标目录并检查
d:
cd "latex\textbook" || (
    echo 无法切换到目标目录，请检查路径是否正确："D:\latex\textbook"
    pause
    exit /b
)

:: 输出当前路径，确保已经成功进入目标目录
echo 当前目录为：%cd%

:: 如果没有成功进入目标目录，显示错误信息
if not "%cd%"=="D:\latex\textbook" (
    echo 错误：没有进入目标目录！
    pause
    exit /b
)

:: 检查是否为 Git 仓库
git rev-parse --is-inside-work-tree >nul 2>&1 || (
    echo 当前目录不是 Git 仓库，请确保路径正确。
    pause
    exit /b
)

:: 获取当前日期和时间（使用 %date% 和 %time% 环境变量）
for /f "tokens=1-4 delims=/- " %%a in ("%date%") do (
    set year=%%a
    set month=%%b
    set day=%%c
)
for /f "tokens=1-2 delims=:." %%a in ("%time%") do (
    set hour=%%a
    set minute=%%b
)

:: 格式化日期和时间
set DATE=%year%-%month%-%day%
set TIME=%hour%:%minute%

:: 输出当前日期和时间
echo 当前日期时间为：%DATE% %TIME%

:: 执行 Git status，检查是否有更改
git status --porcelain >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 检查 Git 状态失败，可能是网络问题或配置错误。
    pause
    exit /b
)

:: 如果有更改，则执行 Git 添加
git add *.pdf >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo git add 命令执行失败，请检查是否有文件需要提交。
    pause
    exit /b
)

:: 执行 Git 提交
git commit -m "auto commit %DATE% %TIME%" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo git commit 命令执行失败，可能没有任何更改需要提交。
    pause
    exit /b
)

:: 执行 Git 推送
git push >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo git push 命令执行失败，可能是网络问题或远程仓库配置错误。
    pause
    exit /b
)

:: 输出成功信息并记录日志
echo 提交并推送成功！>> "D:\latex\textbook\commit_log.txt"
echo 提交时间：%DATE% %TIME% >> "D:\latex\textbook\commit_log.txt"
pause
