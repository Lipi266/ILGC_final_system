; ============================================================================
; ILGC Workplace Monitor - Inno Setup Script
; ============================================================================
; This script creates a Windows installer for the ILGC application
;
; Prerequisites:
; - Inno Setup 6.x installed (https://jrsoftware.org/isinfo.php)
; - ILGC-Workplace.exe built in dist/ folder
;
; Usage:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_windows.iss
; ============================================================================

#define MyAppName "ILGC Workplace Monitor"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "ILGC Research"
#define MyAppURL "https://github.com/youruser/ilgc"
#define MyAppExeName "ILGC-Workplace.exe"
#define MyAppAssocName MyAppName + " File"
#define MyAppAssocExt ".ilgc"
#define MyAppAssocKey StringChange(MyAppAssocName, " ", "") + MyAppAssocExt

[Setup]
; Application information
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases

; Installation settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
InfoBeforeFile=
InfoAfterFile=

; Output settings
OutputDir=Output
OutputBaseFilename=ILGC-Setup-Windows
SetupIconFile=resources\icon.ico
Compression=lzma2
SolidCompression=yes

; Windows compatibility
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Uninstall settings
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Main executable
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Icon file (if exists)
Source: "resources\icon.ico"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Windows-specific files
Source: "windows\*"; DestDir: "{app}\windows"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Note: The PyInstaller executable already bundles most dependencies
; Additional data files would be copied here if needed

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon

; Desktop shortcut
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; Start Menu - Uninstall shortcut
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Option to launch app after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up any generated files
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\details"
Type: filesandordirs; Name: "{app}\feedback"
Type: filesandordirs; Name: "{app}\collated"
Type: filesandordirs; Name: "{app}\screenshot"
Type: filesandordirs; Name: "{app}\watch"
Type: filesandordirs; Name: "{app}\interventions"

[Code]
// ============================================================================
// Custom Pascal Script for additional functionality
// ============================================================================

var
  PermissionsPage: TOutputMsgMemoWizardPage;

procedure InitializeWizard;
begin
  // Create a custom page for permission information
  PermissionsPage := CreateOutputMsgMemoPage(wpInfoAfter,
    'Important: Permissions Required',
    'The application requires the following permissions to function properly:',
    'Please grant the following permissions when prompted:',
    '1. CAMERA ACCESS' + #13#10 +
    '   Required for monitoring user presence and engagement.' + #13#10 +
    '   Go to: Settings > Privacy > Camera > Enable for ILGC' + #13#10 + #13#10 +
    '2. NOTIFICATIONS' + #13#10 +
    '   Required for intervention alerts.' + #13#10 +
    '   Go to: Settings > System > Notifications > Enable for ILGC' + #13#10 + #13#10 +
    '3. BLUETOOTH (Optional)' + #13#10 +
    '   Required if using a heart rate monitor.' + #13#10 +
    '   Go to: Settings > Devices > Bluetooth > Enable' + #13#10 + #13#10 +
    'Note: You can change these settings at any time in Windows Settings.');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Post-installation tasks could go here
    // For example, registering with Windows Firewall
  end;
end;

// Check if Visual C++ Redistributable is installed (optional)
function IsVCRedistInstalled: Boolean;
var
  Installed: Cardinal;
begin
  Result := False;
  // Check for VC++ 2015-2022 Redistributable
  if RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
    Result := (Installed = 1);
  if not Result then
    if RegQueryDWordValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
      Result := (Installed = 1);
end;
