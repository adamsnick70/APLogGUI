; Inno Setup script for AP Log Plotter (ToDo.txt section 10).
;
; Per-user install (no admin prompt, no UAC) - installs to
; %LocalAppData%\Programs\AP Log Plotter, matching the "installers can update
; themselves without admin" direction noted for the future auto-update flow.
;
; Build packaging\windows\dist\AP Log Plotter\ first (packaging\windows\
; build.ps1), then compile this with:
;   ISCC packaging\windows\installer.iss
;
; AppVersion defaults to a placeholder for a manual local build - CI passes
; the real stamped value (see tools/stamp_version.py) with
; `ISCC /DAppVersion=2026.07.23+abc1234 installer.iss`.

#define AppName "AP Log Plotter"
#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#define AppExeName "AP Log Plotter.exe"
#define DistDir "dist\AP Log Plotter"

[Setup]
AppId={{9C6C8C2B-9E9E-4C9A-9C7A-2E3B9C7B7A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Nick Adams
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
OutputDir=installer_output
OutputBaseFilename=AP-Log-Plotter-Setup
SetupIconFile=..\..\assets\icons\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// Legacy-install detection & config migration (ToDo.txt section 12).
//
// install_windows.ps1 never registered a real "installed program" entry -
// it just dropped a Start Menu shortcut whose WorkingDirectory points at
// the git-cloned repo it was run from, alongside that repo's config.json.
// [Icons] below claims that exact same shortcut path, so the old shortcut
// gets naturally overwritten with no extra code needed for that part - the
// only thing this section has to do by hand is carry ap_version/last_dir
// over into the new install's config before the old shortcut disappears.
//
// Detection reads the OLD shortcut in InitializeSetup(), before Setup has
// touched anything (so it's guaranteed to still be the old one, not a new
// one [Icons] just created) - the actual config file write is deferred to
// CurStepChanged(ssPostInstall) so nothing is written if the user cancels.
var
  GLegacyApVersion, GLegacyLastDir, GLegacyWorkDir: string;

function GetLegacyShortcutWorkingDir(const LnkPath: string): string;
var
  WshShell, Shortcut: Variant;
begin
  Result := '';
  try
    WshShell := CreateOleObject('WScript.Shell');
    Shortcut := WshShell.CreateShortcut(LnkPath);
    Result := Shortcut.WorkingDirectory;
  except
    Result := '';
  end;
end;

// config.json is written by Python's json.dump(cfg, f) with its default
// separators - `{"key": "value", "key2": "value2"}` - so a value is always
// found between `"<key>": "` and the next `"`. Returned as-is, still
// JSON-escaped (e.g. last_dir's backslashes as \\), since it's pasted
// straight into another JSON string literal below, not displayed raw.
function ExtractJsonStringValue(const Json, Key: string): string;
var
  Marker: string;
  StartPos, EndPos: Integer;
begin
  Result := '';
  Marker := '"' + Key + '": "';
  StartPos := Pos(Marker, Json);
  if StartPos = 0 then Exit;
  StartPos := StartPos + Length(Marker);
  EndPos := Pos('"', Copy(Json, StartPos, MaxInt));
  if EndPos = 0 then Exit;
  Result := Copy(Json, StartPos, EndPos - 1);
end;

procedure DetectLegacyInstall();
var
  LegacyLnk, OldConfigPath: string;
  OldConfigText: AnsiString;
begin
  LegacyLnk := ExpandConstant('{userappdata}\Microsoft\Windows\Start Menu\Programs\{#AppName}.lnk');
  if not FileExists(LegacyLnk) then Exit;

  GLegacyWorkDir := GetLegacyShortcutWorkingDir(LegacyLnk);
  if GLegacyWorkDir = '' then Exit;

  OldConfigPath := AddBackslash(GLegacyWorkDir) + 'config.json';
  if not FileExists(OldConfigPath) then Exit;
  if not LoadStringFromFile(OldConfigPath, OldConfigText) then Exit;

  GLegacyApVersion := ExtractJsonStringValue(OldConfigText, 'ap_version');
  GLegacyLastDir := ExtractJsonStringValue(OldConfigText, 'last_dir');
end;

procedure ApplyLegacyMigrationIfDetected();
var
  NewConfigDir, NewConfigPath, NewConfigText: string;
  Parts: string;
begin
  if (GLegacyApVersion = '') and (GLegacyLastDir = '') then Exit;

  NewConfigDir := ExpandConstant('{userappdata}\{#AppName}');
  NewConfigPath := NewConfigDir + '\config.json';
  // Never overwrite settings the new app may have already written on a
  // prior run of this same installer/app - migration only seeds a config
  // that doesn't exist yet.
  if FileExists(NewConfigPath) then Exit;

  Parts := '';
  if GLegacyApVersion <> '' then
    Parts := Parts + '"ap_version": "' + GLegacyApVersion + '"';
  if GLegacyLastDir <> '' then
  begin
    if Parts <> '' then Parts := Parts + ', ';
    Parts := Parts + '"last_dir": "' + GLegacyLastDir + '"';
  end;
  NewConfigText := '{' + Parts + '}';

  ForceDirectories(NewConfigDir);
  SaveStringToFile(NewConfigPath, NewConfigText, False);

  MsgBox('A previous AP Log Plotter install was found at:'#13#10 + GLegacyWorkDir + #13#10#13#10 +
    'Its AccessPort version and last-used log folder have been carried over ' +
    'to this install. The old checkout was left untouched and can be deleted ' +
    'manually if you no longer need it (its packages were not modified either).',
    mbInformation, MB_OK);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  DetectLegacyInstall();
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    ApplyLegacyMigrationIfDetected();
end;
