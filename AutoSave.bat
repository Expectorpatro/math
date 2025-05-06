@echo off
title Git Auto Commit Debug

:: �л���Ŀ��Ŀ¼�����
d:
cd "latex\textbook" || (
    echo �޷��л���Ŀ��Ŀ¼������·���Ƿ���ȷ��"D:\latex\textbook"
    pause
    exit /b
)

:: �����ǰ·����ȷ���Ѿ��ɹ�����Ŀ��Ŀ¼
echo ��ǰĿ¼Ϊ��%cd%

:: ���û�гɹ�����Ŀ��Ŀ¼����ʾ������Ϣ
if not "%cd%"=="D:\latex\textbook" (
    echo ����û�н���Ŀ��Ŀ¼��
    pause
    exit /b
)

:: ����Ƿ�Ϊ Git �ֿ�
git rev-parse --is-inside-work-tree >nul 2>&1 || (
    echo ��ǰĿ¼���� Git �ֿ⣬��ȷ��·����ȷ��
    pause
    exit /b
)

:: ��ȡ��ǰ���ں�ʱ�䣨ʹ�� %date% �� %time% ����������
for /f "tokens=1-4 delims=/- " %%a in ("%date%") do (
    set year=%%a
    set month=%%b
    set day=%%c
)
for /f "tokens=1-2 delims=:." %%a in ("%time%") do (
    set hour=%%a
    set minute=%%b
)

:: ��ʽ�����ں�ʱ��
set DATE=%year%-%month%-%day%
set TIME=%hour%:%minute%

:: �����ǰ���ں�ʱ��
echo ��ǰ����ʱ��Ϊ��%DATE% %TIME%

:: ִ�� Git status������Ƿ��и���
git status --porcelain >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ��� Git ״̬ʧ�ܣ�������������������ô���
    pause
    exit /b
)

:: ����и��ģ���ִ�� Git ���
git add *.pdf >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo git add ����ִ��ʧ�ܣ������Ƿ����ļ���Ҫ�ύ��
    pause
    exit /b
)

:: ִ�� Git �ύ
git commit -m "auto commit %DATE% %TIME%" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo git commit ����ִ��ʧ�ܣ�����û���κθ�����Ҫ�ύ��
    pause
    exit /b
)

:: ִ�� Git ����
git push >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo git push ����ִ��ʧ�ܣ����������������Զ�ֿ̲����ô���
    pause
    exit /b
)

:: ����ɹ���Ϣ����¼��־
echo �ύ�����ͳɹ���>> "D:\latex\textbook\commit_log.txt"
echo �ύʱ�䣺%DATE% %TIME% >> "D:\latex\textbook\commit_log.txt"
pause
