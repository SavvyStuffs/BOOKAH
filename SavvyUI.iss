; ──────────────────────────────────────────────────────────
; SavvyUI Sidecar — auto-generated for project
; Include this file in your main .iss script:
;   #include "SavvyUI.iss"
;
; ── REQUIRED: Define the installed app's exe name in your main script:
;   #define SavvyUI_AppExe "MyApp.exe"
; ──────────────────────────────────────────────────────────

[Files]
Source: "UI_Bridge.dll"; DestDir: "{tmp}"; Flags: dontcopy
Source: "WebView2Loader.dll"; DestDir: "{tmp}"; Flags: dontcopy
Source: "SavvyUI_Theme.html"; DestDir: "{tmp}"; Flags: dontcopy

[Code]
// ── App exe name — MUST be defined in your main script BEFORE the #include ──
// This tells SavvyUI which .exe in {app} is your app.
// Add this line to your main .iss (before #include "SavvyUI.iss"):
//
//   #define SavvyUI_AppExe "YourApp.exe"
//
#ifndef SavvyUI_AppExe
  #error "SavvyUI: #define SavvyUI_AppExe is required in your main .iss script. Example: #define SavvyUI_AppExe 'MyApp.exe'"
#endif

// ── Import the bridge DLL functions (pure C++ native, no .NET dependency) ──
function ShowSavvyUI(HTMLPath: String; PayloadBuffer: String; BufferSize: Integer; Width, Height: Integer; Shape: String; Rounded: Boolean): Boolean;
  external 'ShowUI@{tmp}\UI_Bridge.dll stdcall delayload loadwithalteredsearchpath';

// ── Signal the WebView2 window that installation is complete ──
procedure SignalSavvyUI;
  external 'SignalUI@{tmp}\UI_Bridge.dll stdcall delayload loadwithalteredsearchpath';

// ── Set the app launch path for the bridge ──
procedure SetSavvyLaunchPath(Path: String);
  external 'SetLaunchPath@{tmp}\UI_Bridge.dll stdcall delayload loadwithalteredsearchpath';

// ── Block until the user clicks "Finish" on the finish overlay ──
procedure WaitSavvyFinish;
  external 'WaitForFinish@{tmp}\UI_Bridge.dll stdcall delayload loadwithalteredsearchpath';

// ── Clean up the WebView2 bridge to prevent zombie Edge processes ──
procedure CloseSavvyUI;
  external 'CloseUI@{tmp}\UI_Bridge.dll stdcall delayload loadwithalteredsearchpath';

// ── Shell Link creation helper (COM-based, works without external declarations) ──
procedure CreateShellLink(ShortcutPath, Description, Filename, Params, WorkingDir: String; IconIndex: Integer; ShowCmd: Integer);
var
  ShellObj: Variant;
  Link: Variant;
  DirName: String;
begin
  // Ensure parent directory exists
  DirName := ExtractFilePath(ShortcutPath);
  if DirName <> '' then ForceDirectories(DirName);

  ShellObj := CreateOleObject('WScript.Shell');
  Link := ShellObj.CreateShortcut(ShortcutPath);
  Link.TargetPath := Filename;
  Link.Description := Description;
  if Params <> '' then Link.Arguments := Params;
  if WorkingDir <> '' then Link.WorkingDirectory := WorkingDir;
  if IconIndex <> 0 then Link.IconLocation := Filename + ',' + IntToStr(IconIndex);
  Link.Save;
end;

// ── Simple JSON value extractor ──
function GetJsonValue(Json, Key: String): String;
var
  P: Integer;
  Start: Integer;
  SearchKey: String;
  EndP: Integer;
begin
  Result := '';
  SearchKey := '"' + Key + '":';
  P := Pos(SearchKey, Json);
  if P = 0 then
  begin
    SearchKey := '"' + Key + '" :';
    P := Pos(SearchKey, Json);
  end;
  if P > 0 then
  begin
    Start := P + Length(SearchKey);
    while (Start <= Length(Json)) and ((Json[Start] = ' ') or (Json[Start] = #9) or (Json[Start] = #10) or (Json[Start] = #13)) do
      Start := Start + 1;

    if (Start <= Length(Json)) and (Json[Start] = '"') then
    begin
      // String value
      Start := Start + 1;
      EndP := Start;
      while (EndP <= Length(Json)) and (Json[EndP] <> '"') do
      begin
        if (EndP < Length(Json)) and (Json[EndP] = '\') then
          EndP := EndP + 2
        else
          EndP := EndP + 1;
      end;
      Result := Copy(Json, Start, EndP - Start);
    end
    else
    begin
      // Numeric/boolean value
      EndP := Start;
      while (EndP <= Length(Json)) and (Json[EndP] <> ',') and (Json[EndP] <> '}') and (Json[EndP] <> ' ') and (Json[EndP] <> #9) do
        EndP := EndP + 1;
      Result := Copy(Json, Start, EndP - Start);
    end;
  end;
end;

var
  SavvyUI_CreateDesktopIcon: String;
  SavvyUI_RunPostInstall: String;

// ── Auto-skip all wizard pages except Installing ──
// This lets Inno's page engine run but the user never sees the wizard.
// We handle everything through the HTML UI and the JSON payload.
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID <> wpInstalling);
end;

procedure InitializeWizard;
var
  UIPayload: String;
  HTMLPath: String;
  PayloadLen: Integer;
  i: Integer;
  JsonStr: String;
  DesignWidth, DesignHeight: Integer;
  DesignShape: String;
  DesignRounded: Boolean;
begin
  // Hide the standard Inno Setup wizard.
  WizardForm.Visible := False;
  WizardForm.Width := 0;
  WizardForm.Height := 0;

  // Extract bridge files
  ExtractTemporaryFile('SavvyUI_Theme.html');
  ExtractTemporaryFile('UI_Bridge.dll');
  ExtractTemporaryFile('WebView2Loader.dll');

  HTMLPath := ExpandConstant('{tmp}\SavvyUI_Theme.html');
  UIPayload := StringOfChar(#0, 8192);
  
  // These values are injected by the Designer during export
  DesignWidth := 800;
  DesignHeight := 600;
  DesignShape := 'CIRCLE';
  DesignRounded := False;

  if ShowSavvyUI(HTMLPath, UIPayload, Length(UIPayload), DesignWidth, DesignHeight, DesignShape, DesignRounded) then
  begin
    // Find actual string length (C++ writes a null-terminated string into the buffer)
    PayloadLen := 0;
    for i := 1 to Length(UIPayload) do
    begin
      if UIPayload[i] = #0 then
      begin
        PayloadLen := i - 1;
        Break;
      end;
    end;
    if PayloadLen > 0 then
      UIPayload := Copy(UIPayload, 1, PayloadLen);
    Log('SavvyUI: User confirmed. Payload: ' + UIPayload);

    // Restore the wizard but move it off-screen.
    // This keeps Inno's internal event loop active so the installation proceeds,
    // but the user never sees the window.
    WizardForm.Visible := True;
    WizardForm.Left := -10000;
    WizardForm.Top := -10000;

    // ── Data Binding: map JSON values back to Inno Setup ──
    SavvyUI_CreateDesktopIcon := GetJsonValue(UIPayload, 'CreateDesktopIcon');
    SavvyUI_RunPostInstall := GetJsonValue(UIPayload, 'RunPostInstall');

    // Developer note: Access bound values via SavvyUI_<VariableName> in your scripts
  end
  else
  begin
    Log('SavvyUI: User cancelled.');
    WizardForm.Close;
    Abort;
  end;
end;

// ── Clean up the WebView2 bridge to prevent zombie Edge processes ──
// Don't close the window here — the finish page handles its own closing
// when the user clicks "Finish". COM teardown happens in WM_DESTROY.
procedure DeinitializeSetup;
begin
  Log('SavvyUI: DeinitializeSetup called (finish page will handle cleanup)');
end;

// ── Handle post-install tasks (desktop icon, launch app) ourselves ──
// This bypasses Inno's [Tasks] and [Run] postinstall handling since we
// skipped those wizard pages.
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  AppExe: String;
  AppDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Create desktop shortcut if user selected it
    if SameText(SavvyUI_CreateDesktopIcon, 'true') or SameText(SavvyUI_CreateDesktopIcon, 'True') then
    begin
      AppDir := ExpandConstant('{app}');
      AppExe := AppDir + '\' + ExpandConstant('{#SavvyUI_AppExe}');
      if FileExists(AppExe) then
        CreateShellLink(ExpandConstant('{commondesktop}') + '\' + ChangeFileExt(ExpandConstant('{#SavvyUI_AppExe}'), '.lnk'), '', AppExe, '', AppDir, 0, SW_SHOWNORMAL);
    end;

    // Set launch path for the bridge (used when user checks "Launch after install")
    AppDir := ExpandConstant('{app}');
    AppExe := AppDir + '\' + ExpandConstant('{#SavvyUI_AppExe}');
    if FileExists(AppExe) then SetSavvyLaunchPath(AppExe);

  end
  else if CurStep = ssDone then
  begin
    // Signal the custom UI to show the "Finished" overlay, then block until user clicks Finish
    SignalSavvyUI;
    WaitSavvyFinish;
  end;
end;
