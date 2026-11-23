@echo off
setlocal
cd /d "%~dp0"
if exist "dist\OpenDStroke.exe" (
  start "" "%~dp0dist\OpenDStroke.exe"
  exit /b
)
call "%~dp0RUN_DEBUG.bat"
exit /b %errorlevel%
