@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
py -3 --version >nul 2>nul && set "PY=py -3"
%PY% -c "import tkinter as t; root=t.Tk(); root.destroy()"
if errorlevel 1 goto tk_error
%PY% OpenDStroke.py %*
if not errorlevel 1 exit /b 0
echo Startup log: %LOCALAPPDATA%\Open DStroke\startup_error.log
pause
exit /b 1

:tk_error
echo Open DStroke source requires Python 3.10 or later with working Tcl/Tk.
echo Run dist\OpenDStroke.exe or use the Windows installer.
pause
exit /b 1
