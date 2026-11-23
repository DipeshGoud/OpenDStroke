#define AppName "Open DStroke"
#define AppVersion "2.1.1"
#define AppExe "OpenDStroke.exe"

[Setup]
AppId={{8C951DEA-F093-44E7-971D-B8AE3B4FB383}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Dipesh Goud
AppPublisherURL=https://github.com/DipeshGoud/OpenDStroke
AppSupportURL=https://github.com/DipeshGoud/OpenDStroke/issues
DefaultDirName={localappdata}\Programs\Open DStroke
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
MinVersion=10.0
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=dist
OutputBaseFilename=OpenDStroke-Setup
SetupIconFile=OpenDStroke.ico
LicenseFile=LICENSE
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function StopRunningApp(): Boolean;
var
  AppPath: String;
  ExitCode: Integer;
begin
  AppPath := ExpandConstant('{app}\{#AppExe}');
  Result := True;
  if FileExists(AppPath) then
    Result := Exec(AppPath, '--stop', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) and (ExitCode = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not StopRunningApp() then
    Result := 'Exit Open DStroke before continuing setup.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := StopRunningApp();
  if not Result then
    SuppressibleMsgBox('Exit Open DStroke before uninstalling it.', mbError, MB_OK, IDOK);
end;
