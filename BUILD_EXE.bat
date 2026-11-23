@echo off
setlocal
cd /d "%~dp0"
title Open DStroke - Windows Builder

echo =====================================
echo   Open DStroke - Build Windows app
echo =====================================
echo.

set "PY=python"
py -3 --version >nul 2>nul && set "PY=py -3"

echo [1/3] Checking Python...
%PY% -c "import sys, struct, tkinter as t; assert sys.version_info >= (3, 10) and struct.calcsize('P') == 8; root=t.Tk(); root.destroy()"
if errorlevel 1 (
  echo ERROR: Install 64-bit Python 3.10 or newer with Tcl/Tk support.
  pause
  exit /b 1
)

echo [2/3] Running unit tests...
%PY% -m unittest discover -s tests
if errorlevel 1 (
  echo ERROR: Unit tests failed. Build cancelled.
  pause
  exit /b 1
)

%PY% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo Installing PyInstaller for build only...
  %PY% -m pip install --upgrade pyinstaller
  if errorlevel 1 (
    echo ERROR: Could not install PyInstaller. Please check your internet connection.
    pause
    exit /b 1
  )
)

echo [3/3] Building one portable EXE...
%PY% -m PyInstaller --noconfirm --clean OpenDStroke.spec
if errorlevel 1 (
  echo ERROR: Build failed. Review error output above.
  pause
  exit /b 1
)

echo.
echo Portable app: "%CD%\dist\OpenDStroke.exe"
if not defined OPEN_DSTROKE_ISCC (
  for %%I in (ISCC.exe) do set "OPEN_DSTROKE_ISCC=%%~$PATH:I"
)
if not defined OPEN_DSTROKE_ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "OPEN_DSTROKE_ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined OPEN_DSTROKE_ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "OPEN_DSTROKE_ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined OPEN_DSTROKE_ISCC (
  echo Install Inno Setup 6 or set OPEN_DSTROKE_ISCC to the full path to ISCC.exe to build the installer.
  pause
  exit /b 0
)
"%OPEN_DSTROKE_ISCC%" OpenDStroke.iss
if errorlevel 1 (
  echo ERROR: Installer build failed.
  pause
  exit /b 1
)
echo Installer: "%CD%\dist\OpenDStroke-Setup.exe"
pause
