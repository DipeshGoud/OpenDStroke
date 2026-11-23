# Open DStroke

Open DStroke is a Windows keyboard and mouse overlay for presentations, recordings, and demos. It displays input locally without storing or sending pressed keys.

[![Release](https://img.shields.io/github/v/release/DipeshGoud/OpenDStroke?color=007acc&logo=github)](https://github.com/DipeshGoud/OpenDStroke/releases/latest)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(64--bit)-blue)](https://github.com/DipeshGoud/OpenDStroke/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Built and maintained by [Dipesh Goud (@DipeshGoud)](https://github.com/DipeshGoud). The official builds are free.

## Download & Install on Windows

Download the latest release directly from the **[Releases Page](https://github.com/DipeshGoud/OpenDStroke/releases/latest)**:

- 📦 **[Download Installer (OpenDStroke-Setup.exe)](https://github.com/DipeshGoud/OpenDStroke/releases/latest/download/OpenDStroke-Setup.exe)** – Recommended for most users. Installs to your user profile (no administrator rights needed) and adds Start menu and optional desktop shortcuts.
- 🚀 **[Download Portable (OpenDStroke.exe)](https://github.com/DipeshGoud/OpenDStroke/releases/latest/download/OpenDStroke.exe)** – Single standalone executable, no installation needed. Run from any folder or USB drive.

### Setup Instructions

1. Run **OpenDStroke-Setup.exe** on 64-bit Windows 10 or 11.
2. Follow setup, then open **Open DStroke** from the Start menu. Setup installs for the current user and offers an optional desktop shortcut.
3. To remove it, use **Windows Settings → Apps → Installed apps → Open DStroke → Uninstall**, or search for **Uninstall Open DStroke** in Start. The uninstaller closes the running app and removes its shortcuts. It keeps your preferences for a future reinstall.

For portable use, simply run **OpenDStroke.exe**. Both builds bundle their Python and Tk runtimes. Launching again brings the existing dashboard forward.

## Use the overlay

- **Keyboard** appears on the upper row. **Mouse clicks and scrolling** appear on the lower row with a blue border. Each row clears independently.
- Rapid clicks of the same button show a count such as **Left click ×2**. The Inputs page controls click counts, keyboard, clicks, scrolling, and the optional cursor ring.
- The Overlay page controls position, display duration, and opacity (20–100%). Drag a visible keycap to move it, or right-click it for more options.
- The Styles page has eight presets and a custom style editor with JSON import and export.
- Press **Ctrl+Shift+O** to pause or resume, and **Ctrl+Shift+K** to show or hide the dashboard. Use **Exit Open DStroke** to close the dashboard and stop the input hooks.

Preferences are saved under **%APPDATA%\Open DStroke**. The app reads a previous KeyHalo settings file when Open DStroke has no settings file yet.

## Run from source or rebuild

- **RUN_DEBUG.bat** runs from source with visible errors. Use 64-bit Python 3.10 or newer with Tcl/Tk support. **RUN_OPEN_DSTROKE.bat** prefers the bundled portable app when present.
- **BUILD_EXE.bat** checks Tcl/Tk, runs the tests, and uses PyInstaller to build the portable app. Install Inno Setup 6 to build the installer from **OpenDStroke.iss**. Set **OPEN_DSTROKE_ISCC** to the path to **ISCC.exe** if it is installed in a custom location.
- GitHub Actions can build both Windows executables with the **Build Open DStroke for Windows** workflow.
- Startup error details are written to **%LOCALAPPDATA%\Open DStroke\startup_error.log** when that folder is writable.

## Contribute

Report a bug through [GitHub Issues](https://github.com/DipeshGoud/OpenDStroke/issues). Include your Open DStroke version, Windows version, and steps to reproduce it. For a code change, open a pull request and run `python -m unittest discover -s tests -v` before submitting. Changes to the desktop UI can also be checked with `python tests/ui_smoke.py` on Windows.

Open DStroke is licensed under MIT. It permits commercial use and redistribution with the license notice. See [LICENSE](LICENSE).
