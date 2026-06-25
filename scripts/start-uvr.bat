@echo off
set "UVR_HOME=D:\AIchatbot\tools\UVR5"
set "TCL_LIBRARY=%UVR_HOME%\tcl"
set "TK_LIBRARY=%UVR_HOME%\tk"
set "PATH=%UVR_HOME%;%PATH%"

cd /d "%UVR_HOME%"
start "" "%UVR_HOME%\UVR.exe"
