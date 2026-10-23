@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_python
".venv\Scripts\python.exe" "scripts\bilibili_quick_control.py" status
set "control_result=%errorlevel%"
goto finished
:missing_python
echo Project Python is missing. Check the .venv folder.
set "control_result=1"
:finished
popd
pause
exit /b %control_result%
