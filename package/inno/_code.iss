#define UNINSTALL_USE_CLEAR_PAGE
#if 0
[Code]
#endif
////////////////////
// Utils          //
////////////////////

procedure DirectoryCopy(SourcePath, DestPath: string);
var
  FindRec: TFindRec;
  SourceFilePath: string;
  DestFilePath: string;
begin
  if FindFirst(SourcePath + '\*', FindRec) then begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then begin
          SourceFilePath := SourcePath + '\' + FindRec.Name;
          DestFilePath := DestPath + '\' + FindRec.Name;
          if FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY = 0 then begin
            if not FileCopy(SourceFilePath, DestFilePath, False) then
              Log(Format('Failed to copy %s to %s', [SourceFilePath, DestFilePath]));
          end else begin
            if DirExists(DestFilePath) or CreateDir(DestFilePath) then begin
              DirectoryCopy(SourceFilePath, DestFilePath);
            end else
              Log(Format('Failed to create %s', [DestFilePath]));
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end else begin
    Log(Format('Failed to list %s', [SourcePath]));
  end;
end;

function StartsWith(SubStr, S: String): Boolean;
begin
   Result := Pos(SubStr, S) = 1;
end;

function StringReplace(S, oldSubString, newSubString: String) : String;
var
  stringCopy : String;
begin
  stringCopy := S; //Prevent modification to the original string
  StringChange(stringCopy, oldSubString, newSubString);
  Result := stringCopy;
end;

function GetCommandlineParam(inParamName: String) : String;
var
   paramNameAndValue: String;
   i: Integer;
begin
   Result := '';

   for i:= 1 to ParamCount do begin
     paramNameAndValue := Lowercase(ParamStr(i));
     if StartsWith(inParamName, paramNameAndValue) then begin
       Result := StringReplace(paramNameAndValue, inParamName + ':', '');
       break;
     end;
   end;
end;

function CheckCommandlineParam(inpn: String) : Boolean;
var
   i: Integer;
begin
   Result := false;

   for i:= 1 to ParamCount do begin
     if Lowercase(inpn) = Lowercase(ParamStr(i)) then begin
       Result := true;
       break;
     end;
   end;
end;

function CheckVCRedist(): Boolean;
var
  Version: Integer;
begin
#ifndef _WIN_XP
  Version := PackVersionComponents(14, 32, 31332, 0);
#if ARCH == "arm64"
  Result := IsMsiProductInstalled('{DC9BAE42-810B-423A-9E25-E4073F1C7B00}', Version);
#else
  if Is64BitInstallMode then
    Result := IsMsiProductInstalled('{36F68A90-239C-34DF-B58C-64B30153CE35}', Version)
  else
    Result := IsMsiProductInstalled('{65E5BD06-6392-3027-8C26-853107D3CF1A}', Version);
#endif
#else
  Version := PackVersionComponents(14, 27, 29114, 0);
  if Is64BitInstallMode then
    Result := IsMsiProductInstalled('{C146EF48-4D31-3C3D-A2C5-1E91AF8A0A9B}', Version)
  else
    Result := IsMsiProductInstalled('{F899BAD3-98ED-308E-A905-56B5338963FF}', Version);
#endif
end;

function ReadBinFile(fileName: String; list: TStringList): Boolean;
var
  fs: TFileStream;
  buff: String;
  len: Word;
  ch: Char;
begin
  Result := False;
  if not FileExists(fileName) then
    Exit;
  list.Clear;
  try
    fs := TFileStream.Create(fileName, fmOpenRead);
  except
    Exit;
  end;
  while fs.Position < fs.Size do begin
    SetLength(buff, 1);
    try
      fs.ReadBuffer(buff, SizeOf(len));
    except
      fs.Free;
      Exit;
    end;
    len := Ord(buff[1]);
    SetLength(buff, len);
    try
      fs.ReadBuffer(buff, len * SizeOf(ch));
    except
      fs.Free;
      Exit;
    end;
    list.Add(buff);
  end;
  Result := True;
  fs.Free;
end;

procedure RemoveExtraFiles();
var
  i: Integer;
  appPath, path: String;
  files: TStringList;
begin
  files := TStringList.Create;
  appPath := ExpandConstant('{app}');
  if ReadBinFile(appPath + '\unins000.bin', files) then begin
    for i := 0 to files.Count - 1 do begin
      if DeleteFile(appPath + files[i]) then begin
        path := ExtractFileDir(files[i]);
        while (path <> '\') do begin
          if not RemoveDir(appPath + path) then
            break;
          path := ExtractFileDir(path);
        end;
      end;
    end;
  end;
  files.Free;
  DeleteFile(appPath + '\unins000.bin');
end;

////////////////////
// Associate Page //
////////////////////

type
  TKeyValue = record
    Key: string;
    Value: string;
  end;
  TArrayOfValues = array of TKeyValue;

var
  OnAudioClick: Boolean;
  ChlbAudio: TNewCheckListBox;
  AudioExtEnabled: Array of Boolean;
  AudioExts: Array of String;
  ExtensionRegistryInfo: array of string;
  AChecked: Boolean;
  associatePage: TWizardPage;
  isFullAssociation: Boolean;

procedure Explode(var Dest: TArrayOfString; Text: String; Separator: String);
var
  i, p: Integer;
begin
  i := 0;
  repeat
    SetArrayLength(Dest, i+1);
    p := Pos(Separator,Text);
    if p > 0 then begin
      Dest[i] := Copy(Text, 1, p-1);
      Text := Copy(Text, p + Length(Separator), Length(Text));
      i := i + 1;
    end else begin
      Dest[i] := Text;
      Text := '';
    end;
  until Length(Text)=0;
end;

// EuroOffice Writer, Sheet, Presentation and PDF (desktop-apps
// win-linux/src/cappidentity.cpp gives the running applications the same
// names and taskbar identities)
function SosIsApp(app: string): Boolean;
begin
  Result := (app = 'writer') or (app = 'sheet') or (app = 'presentation') or (app = 'pdf');
end;

function SosAppKey(app: string): string;
begin
  if SosIsApp(app) then Result := Uppercase(Copy(app, 1, 1)) + Copy(app, 2, Length(app) - 1)
  else Result := '';
end;

function SosAppName(app: string): string;
begin
  if app = 'pdf' then Result := 'EuroOffice PDF'
  else if SosIsApp(app) then Result := 'EuroOffice ' + SosAppKey(app)
  else Result := '{#sAppName}';
end;

function SosAppUserModelId(app: string): string;
begin
  if SosIsApp(app) then Result := '{#APP_ID_PREFIX}.' + SosAppKey(app)
  else Result := '{#APP_USER_MODEL_ID}';
end;

function SosAppIcon(app: string): string;
begin
  if SosIsApp(app) then Result := ExpandConstant('{app}\icons\') + app + '.ico'
  else Result := ExpandConstant('{app}\{#iconsExe},33');
end;

function SosOpenCommand(app: string): string;
begin
  if SosIsApp(app) then Result := ExpandConstant('"{app}\{#iconsExe}"') + ' --app=' + app + ' "%1"'
  else Result := ExpandConstant('"{app}\{#iconsExe}"') + ' "%1"';
end;

procedure initExtensions;
var
  prefix: string;
begin
#ifdef _EuroOffice
  SetArrayLength(AudioExts, 29);
#else
  SetArrayLength(AudioExts, 28);
#endif
  SetArrayLength(AudioExtEnabled,  GetArrayLength(AudioExts));

  AudioExts[0]  := 'DOC';
  AudioExts[1]  := 'DOCX';
  AudioExts[2]  := 'XLS';
  AudioExts[3]  := 'XLSX';
  AudioExts[4]  := 'PPT';
  AudioExts[5]  := 'PPTX';
  AudioExts[6]  := 'PPS';
  AudioExts[7]  := 'PPSX';
  AudioExts[8]  := 'ODT';
  AudioExts[9]  := 'ODS';
  AudioExts[10] := 'ODP';
  AudioExts[11] := 'RTF';
//  AudioExts[12] := 'TXT';
  AudioExts[12] := 'CSV';
  AudioExts[13] := 'PDF';
  AudioExts[14] := 'DJVU';
  AudioExts[15] := 'XPS';
  AudioExts[16] := 'POT';
  AudioExts[17] := 'PPTM';
  AudioExts[18] := 'EPUB';
  AudioExts[19] := 'FB2';
  AudioExts[20] := 'DOTX';
  AudioExts[21] := 'OXPS';
  AudioExts[22] := 'XLSB';
  AudioExts[23] := 'FODS';
  AudioExts[24] := 'FODT';
  AudioExts[25] := 'VSDX';
  AudioExts[26] := 'XLSM';
#ifdef _EuroOffice
  AudioExts[27] := 'DOCXF';
  AudioExts[28] := 'TXT';
#else
  AudioExts[27] := 'TXT';
#endif

  SetArrayLength(ExtensionRegistryInfo,  GetArrayLength(AudioExts));

  // ProgID:description:icon index:application (EuroOffice Writer, Sheet,
  // Presentation or PDF opens it; suite: none of them)

  prefix := '{#ASCC_REG_PREFIX}' + '.';

  ExtensionRegistryInfo[0]  := prefix + 'Document.1:'   + ExpandConstant('{cm:extDOC}')             + ':' + '11' + ':' + 'writer';
  ExtensionRegistryInfo[1]  := prefix + 'Document.12:'  + ExpandConstant('{cm:extDOCX}')            + ':' + '7' + ':' + 'writer';
  ExtensionRegistryInfo[2]  := prefix + 'Sheet.1:'      + ExpandConstant('{cm:extXLS}')             + ':' + '22' + ':' + 'sheet';
  ExtensionRegistryInfo[3]  := prefix + 'Sheet.12:'     + ExpandConstant('{cm:extXLSX}')            + ':' + '10' + ':' + 'sheet';
  ExtensionRegistryInfo[4]  := prefix + 'Show.1:'       + ExpandConstant('{cm:extPPT}')             + ':' + '1' + ':' + 'presentation';
  ExtensionRegistryInfo[5]  := prefix + 'Show.12:'      + ExpandConstant('{cm:extPPTX}')            + ':' + '9' + ':' + 'presentation';
  ExtensionRegistryInfo[6]  := prefix + 'SlideShow.1:'  + ExpandConstant('{cm:extPPS}')             + ':' + '2' + ':' + 'presentation';
  ExtensionRegistryInfo[7]  := prefix + 'SlideShow.12:' + ExpandConstant('{cm:extPPSX}')            + ':' + '8' + ':' + 'presentation';
  ExtensionRegistryInfo[8]  := prefix + 'Document.2:'   + ExpandConstant('{cm:extODT}')             + ':' + '18' + ':' + 'writer';
  ExtensionRegistryInfo[9]  := prefix + 'Sheet.2:'      + ExpandConstant('{cm:extODS}')             + ':' + '23' + ':' + 'sheet';
  ExtensionRegistryInfo[10] := prefix + 'Show.2:'       + ExpandConstant('{cm:extODP}')             + ':' + '3' + ':' + 'presentation';
  ExtensionRegistryInfo[11] := prefix + 'Rtf:'          + ExpandConstant('{cm:extRTF}')             + ':' + '19' + ':' + 'writer';
  //ExtensionRegistryInfo[12] := prefix + 'Txt:'                                                      + ':' + '14' + ':' + 'writer';
  ExtensionRegistryInfo[12] := prefix + 'Csv:'          + ExpandConstant('{cm:extCSV}')             + ':' + '24' + ':' + 'sheet';
  ExtensionRegistryInfo[13] := prefix + 'Pdf:'          + ExpandConstant('{cm:extPDF}')             + ':' + '5' + ':' + 'pdf';
  ExtensionRegistryInfo[14] := prefix + 'DjVu:'         + ExpandConstant('{cm:extDJVU}')            + ':' + '4' + ':' + 'pdf';
  ExtensionRegistryInfo[15] := prefix + 'Xps:'          + ExpandConstant('{cm:extXPS}')             + ':' + '6' + ':' + 'pdf';
  ExtensionRegistryInfo[16] := prefix + 'Pot:'          + ExpandConstant('{cm:extPOT}')             + ':' + '26' + ':' + 'presentation';
  ExtensionRegistryInfo[17] := prefix + 'Pptm:'         + ExpandConstant('{cm:extPPTM}')            + ':' + '27' + ':' + 'presentation';
  ExtensionRegistryInfo[18] := prefix + 'Epub:'         + ExpandConstant('{cm:extEPUB}')            + ':' + '28' + ':' + 'writer';
  ExtensionRegistryInfo[19] := prefix + 'Fb2:'          + ExpandConstant('{cm:extFB2}')             + ':' + '29' + ':' + 'writer';
  ExtensionRegistryInfo[20] := prefix + 'Dotx:'         + ExpandConstant('{cm:extDOTX}')            + ':' + '30' + ':' + 'writer';
  ExtensionRegistryInfo[21] := prefix + 'Oxps:'         + ExpandConstant('{cm:extOXPS}')            + ':' + '31' + ':' + 'pdf';
  ExtensionRegistryInfo[22] := prefix + 'Xlsb:'         + ExpandConstant('{cm:extXLSB}')            + ':' + '32' + ':' + 'sheet';
  ExtensionRegistryInfo[23] := prefix + 'Fods:'         + ExpandConstant('{cm:extFODS}')            + ':' + '34' + ':' + 'sheet';
  ExtensionRegistryInfo[24] := prefix + 'Fodt:'         + ExpandConstant('{cm:extFODT}')            + ':' + '35' + ':' + 'writer';
  ExtensionRegistryInfo[25] := prefix + 'Vsdx:'         + ExpandConstant('{cm:extVSDX}')            + ':' + '36' + ':' + 'suite';
  ExtensionRegistryInfo[26] := prefix + 'Xlsm:'         + ExpandConstant('{cm:extXLSM}')            + ':' + '37' + ':' + 'sheet';
#ifdef _EuroOffice
  ExtensionRegistryInfo[27] := prefix + 'Docxf:'        + ExpandConstant('{cm:extDOCXF}')           + ':' + '13' + ':' + 'pdf';
  ExtensionRegistryInfo[28] := prefix + 'Txt:'          + ExpandConstant('{cm:extTXT}')             + ':' + '20' + ':' + 'writer';
#else
  ExtensionRegistryInfo[27] := prefix + 'Txt:'          + ExpandConstant('{cm:extTXT}')             + ':' + '20' + ':' + 'writer';
#endif
end;

procedure ChlbAudioClickCheck(Sender: TObject);
var
  i: Integer;
begin
  if not OnAudioClick then
  begin
    OnAudioClick := True;
    if ChlbAudio.Checked[2] then
    begin
      if not AChecked then
      begin
        AChecked := True;
        for i := 0 to GetArrayLength(AudioExts) - 1 do
        begin
          ChlbAudio.ItemEnabled[i + 3] := True;
          ChlbAudio.Checked[i + 3] := AudioExtEnabled[i];
        end;
      end
      else
      begin
        for i := 0 to GetArrayLength(AudioExts) - 1 do
          AudioExtEnabled[i] := ChlbAudio.Checked[i + 3];
      end;
    end
    else
    begin
      AChecked := False;
      for i := 0 to GetArrayLength(AudioExts) - 1 do
      begin
        ChlbAudio.ItemEnabled[i + 3] := False;
//        ChlbAudio.Checked[i + 3] := ArrAudio[i];
      end;
    end;
    OnAudioClick := False;
    ChlbAudio.Repaint;
  end;
end;

procedure InitializeAssociatePage;
var
  lblAudio: TLabel;
  i: Integer;
  version: TWindowsVersion;
  createPage: Boolean;
  paramSkip: string;

  labelDesc, labelPath: TNewStaticText;
begin
  initExtensions();

  ChlbAudio  := nil;
  createPage := False;
  if not WizardSilent() then begin
    paramSkip := GetCommandlineParam('/skip');
    if (not Length(paramSkip) > 0) or (paramSkip <> 'associates') then begin
      createPage := True;
    end
  end;

  if createPage then begin
    associatePage := CreateCustomPage(wpSelectTasks, CustomMessage('AssociateCaption'), CustomMessage('AssociateDescription'));

    //GetWindowsVersionEx(version);
    //if version.Major < 10 then begin
      lblAudio          := TLabel.Create(associatePage);
      lblAudio.Parent   := associatePage.Surface;
      lblAudio.Caption  := ExpandConstant('{cm:AssociateAudio}');
      lblAudio.AutoSize := True;
      lblAudio.Width    := associatePage.SurfaceWidth;
      lblAudio.WordWrap := True;
      lblAudio.Left     := 0;
      lblAudio.Top      := 0;

      ChlbAudio         := TNewCheckListBox.Create(associatePage);
      ChlbAudio.Parent  := associatePage.Surface;
      ChlbAudio.Left    := 0;
      ChlbAudio.Top     := lblAudio.Top + lblAudio.Height + 4;
      ChlbAudio.Width   := associatePage.SurfaceWidth;
      ChlbAudio.Height  := associatePage.SurfaceHeight - ChlbAudio.Top - 4 - 3;

      ChlbAudio.AddRadioButton(ExpandConstant('{cm:AssociateDont}'), '', 0, False, True, nil);
      ChlbAudio.AddRadioButton(ExpandConstant('{cm:AssociateAll}'),  '', 0, False, True, nil);
      ChlbAudio.AddRadioButton(ExpandConstant('{cm:AssociateSel}'),  '', 0, True,  True, nil);

      AChecked := True;

      for  i := 0 to GetArrayLength(AudioExts) - 1 do
      begin
        ChlbAudio.AddCheckBox(AudioExts[i], '', 1, False, True, False, False, nil);
        AudioExtEnabled[i] := True;
      end;

      OnAudioClick := False;
      ChlbAudio.OnClickCheck := @ChlbAudioClickCheck;

      ChlbAudio.Checked[1] := True;
      ChlbAudioClickCheck(ChlbAudio);
    //end else begin
    //  labelDesc           := TNewStaticText.Create(associatePage);
    //  labelDesc.Parent    := associatePage.Surface;
    //  labelDesc.Width     := associatePage.SurfaceWidth;
    //  labelDesc.WordWrap  := True;
    //  labelDesc.Caption   := ExpandConstant('{cm:warnWin10FileAssociationDesc}');

    //  labelPath           := TNewStaticText.Create(associatePage);
    //  labelPath.Parent    := associatePage.Surface;
    //  labelPath.Top       := labelDesc.Top + labelDesc.Height + ScaleY(8);
    //  labelPath.Width     := associatePage.SurfaceWidth;
    //  labelPath.WordWrap  := True;
    //  labelPath.Caption   := ExpandConstant('{cm:warnWin10FileAssociationPath}');
    //  labelPath.Font.Style := [fsBold];
    //end
  end else begin
    associatePage := nil
  end;

  //vc_desctopiconshow := True;
  //WizardForm.TasksList.OnClickCheck := @OnTasksListClickCheck;
end;

//----------

function isAssociateExtension(index: Integer): Boolean;
begin
  if ChlbAudio = nil then begin
    if isFullAssociation then Result := True
    else Result := False
  end else
    Result := ChlbAudio.Checked[1] or (ChlbAudio.Checked[2] and ChlbAudio.Checked[index + 3]);
end;

//----------

// Default apps: EuroOffice Writer, Sheet, Presentation and PDF are listed
// as four applications, each with the file types it opens
procedure AddToDefaultPrograms;
var
  i, a: integer;
  argsArray: TArrayOfString;
  apps: TArrayOfString;
  capPath: string;
begin
    apps := ['writer', 'sheet', 'presentation', 'pdf'];
    for a := 0 to GetArrayLength(apps) - 1 do begin
      capPath := '{#APP_REG_PATH}\Apps\' + SosAppKey(apps[a]) + '\Capabilities';
      RegWriteStringValue(HKEY_LOCAL_MACHINE, capPath, 'ApplicationDescription', SosAppName(apps[a]));
      RegWriteStringValue(HKEY_LOCAL_MACHINE, capPath, 'ApplicationIcon', SosAppIcon(apps[a]));
      RegWriteStringValue(HKEY_LOCAL_MACHINE, capPath, 'ApplicationName', SosAppName(apps[a]));

      for i := 0 to GetArrayLength(AudioExts) - 1 do begin
        Explode(argsArray, ExtensionRegistryInfo[i],':');
        if argsArray[3] = apps[a] then
          RegWriteStringValue(HKEY_LOCAL_MACHINE, capPath + '\FileAssociations', '.' + LowerCase(AudioExts[i]), argsArray[0]);
      end;

      RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\RegisteredApplications', SosAppName(apps[a]), capPath);
    end;

    // the suite itself no longer takes file types
    RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, '{#APP_REG_PATH}\Capabilities');
    RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\RegisteredApplications', '{#ASCC_REG_REGISTERED_APP_NAME}');
end;

function TryGetValue(const KeyValueList: TArrayOfValues; const Key: string; var Value: string): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 0 to GetArrayLength(KeyValueList) - 1 do
    if KeyValueList[I].Key = Key then
    begin
      Result := True;
      Value := KeyValueList[I].Value;
      Exit;
    end;
end;

procedure AddKeyValue(const destarray: TArrayOfValues; const key, value: string);
var
  Index: Integer;
begin
  Index := GetArrayLength(destarray);
  SetArrayLength(destarray, Index + 1);

  destarray[Index].Key := key;
  destarray[Index].Value := value;
end;

procedure AddContextMenuNewItems;
var
  lang, dir, regpath, progpath: String;
  args, values: TArrayOfString;
  version: TWindowsVersion;
  found: Boolean;
  i: Integer;
begin
  lang := ExpandConstant('{cm:AppLocale}');
  case lang of
    'ar-SA', 'az-Latn-AZ', 'bg-BG', 'ca-ES', 'cs-CZ', 'da-DK', 'de-DE',
    'el-GR', 'en-GB', 'en-US', 'es-ES', 'eu-ES', 'fi-FI', 'fr-FR',
    'gl-ES', 'he-IL', 'hu-HU', 'hy-AM', 'id-ID', 'it-IT', 'ja-JP',
    'ko-KR', 'lv-LV', 'ms-MY', 'nb-NO', 'nl-NL', 'pl-PL', 'pt-BR',
    'pt-PT', 'ro-RO', 'ru-RU', 'si-LK', 'sk-SK', 'sl-SI', 'sq-AL',
    'sr-Cyrl-RS', 'sr-Latn-RS', 'sv-SE', 'tr-TR', 'uk-UA', 'ur-PK', 'vi-VN',
    'zh-CN', 'zh-TW' : dir := lang;
  else
    dir := 'default';
  end;

  args := ['new.docx:.docx:.Document.12:7:1000:1100',
           'new.pptx:.pptx:.Show.12:9:1002:1102',
           'new.xlsx:.xlsx:.Sheet.12:10:1001:1101'
#ifdef _EuroOffice
           ,'new.pdf:.pdf:.Pdf:5:1003:1103'
#endif
           ];

  GetWindowsVersionEx(version);
  progpath := ExpandConstant('{app}\converter\empty\' + dir);
  for i := 0 to GetArrayLength(args) - 1 do begin
     Explode(values, args[i],':');
     regpath := ExpandConstant('Software\Classes\' + values[1] + '\{#ASCC_REG_PREFIX}' + values[2] + '\ShellNew');
     if not RegKeyExists(HKEY_LOCAL_MACHINE, regpath) then begin
       RegWriteStringValue(HKEY_LOCAL_MACHINE, regpath, 'IconPath', ExpandConstant('{app}\{#iconsExe},' + values[3]));
       RegWriteStringValue(HKEY_LOCAL_MACHINE, regpath, 'FileName', progpath + '\' + values[0]);
       RegWriteStringValue(HKEY_LOCAL_MACHINE, regpath, 'MenuText', ExpandConstant('@{app}\{#iconsExe},-' + values[4]));
       RegWriteStringValue(HKEY_LOCAL_MACHINE, regpath, 'ItemName', ExpandConstant('@{app}\{#iconsExe},-' + values[5]));
     end;
     // Explorer's New menu needs the type to name a ProgID; one that already
     // has an application keeps it unless the user associated it (DoPostInstall)
     if (version.Major = 10) and not RegValueExists(HKEY_LOCAL_MACHINE, 'Software\Classes\' + values[1], '') then
       RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\' + values[1], '', '{#ASCC_REG_PREFIX}' + values[2]);
  end;
end;

// Windows 10 and 11 keep each user's own choice of default application
// (UserChoice), which setup cannot change. The supported way for an
// organisation is a default associations file named by policy: Windows
// applies it to every user at sign-in. Setup writes the file for the file
// types it associated and names it in the policy, unless another file is
// already configured there (by a domain policy, say) or /NOASSOCPOLICY is
// given. Uninstall takes both away again.
function SosAssocXmlPath: string;
begin
  Result := ExpandConstant('{app}\DefaultAssociations.xml');
end;

procedure SetDefaultAssociationsPolicy(entries: string);
var
  current: string;
begin
  SaveStringToFile(SosAssocXmlPath, '<?xml version="1.0" encoding="UTF-8"?>' + #13#10 +
                   '<DefaultAssociations>' + #13#10 + entries + '</DefaultAssociations>' + #13#10, False);
  if CheckCommandlineParam('/NOASSOCPOLICY') then
    exit;
  current := '';
  RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Policies\Microsoft\Windows\System', 'DefaultAssociationsConfiguration', current);
  if (Length(current) = 0) or (CompareText(current, SosAssocXmlPath) = 0) then
    RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Policies\Microsoft\Windows\System', 'DefaultAssociationsConfiguration', SosAssocXmlPath)
  else
    Log('Default associations policy already names ' + current + '; left as it is');
end;

procedure RemoveDefaultAssociationsPolicy;
var
  current: string;
begin
  current := '';
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Policies\Microsoft\Windows\System', 'DefaultAssociationsConfiguration', current) and
        (CompareText(current, SosAssocXmlPath) = 0) then
    RegDeleteValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Policies\Microsoft\Windows\System', 'DefaultAssociationsConfiguration');
  DeleteFile(SosAssocXmlPath);
end;

procedure DoPostInstall();
var
  i, errorCode: Integer;
  ext, progId1, progId2, progId3, assocArg, assocXml: string;
  argsArray: TArrayOfString;
  cleanExts, extensionInfo: TArrayOfString;
  version: TWindowsVersion;
  prefix, str: string;
begin
    isFullAssociation := CheckCommandlineParam('/FULLASSOCIATION');
    if (associatePage = nil) and isFullAssociation then begin
      initExtensions();
    end;

    assocArg := '';
    assocXml := '';
    GetWindowsVersionEx(version);
    for  i := 0 to GetArrayLength(AudioExts) - 1 do
    begin
      Explode(argsArray, ExtensionRegistryInfo[i],':');

      // checking existance is temporary locked to rewrite new icons indexes
      //if not RegKeyExists(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0]) then begin
        if Length(argsArray[1]) <> 0 then
          RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0], '', argsArray[1]);

        // the file type opens in its own application (EuroOffice Writer,
        // Sheet, Presentation or PDF), which also owns its taskbar button
        RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0], 'AppUserModelID', SosAppUserModelId(argsArray[3]));
        RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0] + '\DefaultIcon', '', ExpandConstant('{app}\{#iconsExe},' + argsArray[2]));
        RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0] + '\shell\open\command', '', SosOpenCommand(argsArray[3]));
        RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0] + '\shell\open', 'FriendlyAppName', SosAppName(argsArray[3]));
        RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0] + '\Application', 'ApplicationName', SosAppName(argsArray[3]));
        if (version.Major = 10) and (version.Minor = 0) and (version.Build < 22000) then begin
          RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0] + '\Application', 'ApplicationIcon', SosAppIcon(argsArray[3]));
        end;
      //end;

      ext := LowerCase(AudioExts[i]);

      if isAssociateExtension(i) then
      begin
        // the file type opens in its application from now on: remember what
        // opened it before (uninstall puts that back), then take it over
        progId1 := '';
        if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext, '', progId1) and
              (Length(progId1) <> 0) and (CompareText(progId1, argsArray[0]) <> 0) and
              not RegValueExists(HKEY_LOCAL_MACHINE, '{#APP_REG_PATH}\PreviousAssociations', '.' + ext) then
          RegWriteStringValue(HKEY_LOCAL_MACHINE, '{#APP_REG_PATH}\PreviousAssociations', '.' + ext, progId1);
        RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext, '', argsArray[0]);

        if not RegValueExists(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext + '\OpenWithProgids', argsArray[0]) then
          RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext + '\OpenWithProgids', argsArray[0], '');

        // the installing user's earlier choice of another application
        progId2 := '';
        if RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Classes\.' + ext, '', progId2) and
              (Length(progId2) <> 0) and (CompareText(progId2, argsArray[0]) <> 0) then
          RegWriteStringValue(HKEY_CURRENT_USER, 'Software\Classes\.' + ext, '', argsArray[0]);
        progId3 := '';
        if RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.' + ext + '\UserChoice', 'ProgId', progId3) and
              (CompareText(progId3, argsArray[0]) <> 0) then
          // Windows may refuse this (its UCPD driver guards PDF); the
          // default associations policy below covers it at next sign-in
          if not RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.' + ext + '\UserChoice') then
            Log('Windows kept the user''s choice of ' + progId3 + ' for .' + ext + '; the default associations policy applies at next sign-in')
          else
            Log('Cleared the user''s choice of ' + progId3 + ' for .' + ext);

        assocXml := assocXml + '  <Association Identifier=".' + ext + '" ProgId="' + argsArray[0] +
                    '" ApplicationName="' + SosAppName(argsArray[3]) + '" />' + #13#10;
      end;
    end;

    if Length(assocXml) <> 0 then
      SetDefaultAssociationsPolicy(assocXml);

  AddToDefaultPrograms;
  AddContextMenuNewItems;

#ifndef _EuroOffice
  //TODO: for bug 55795. remove for ver 7.3
  SetArrayLength(cleanExts, 1);
  SetArrayLength(extensionInfo, 1);

  prefix := '{#ASCC_REG_PREFIX}' + '.';

  cleanExts[0]  := 'DOCXF';

  extensionInfo[0] := prefix + 'Docxf:' + ExpandConstant('{cm:extDOCXF}') + ':' + '13';

  for  i := 0 to GetArrayLength(cleanExts) - 1 do
  begin
    Explode(argsArray, extensionInfo[i],':');
    RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0]);

    ext := LowerCase(cleanExts[i]);
    RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext + '\OpenWithProgids', argsArray[0]);
    RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext + '\OpenWithProgids', ExpandConstant('{#ASSOC_PROG_ID}'));

    RegQueryStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext, '', str);
    if CompareText(str, argsArray[0]) = 0 then
      RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext, '');

    RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Classes\.' + ext, '', str);
    if CompareText(str, argsArray[0]) = 0 then
      RegDeleteValue(HKEY_CURRENT_USER, 'Software\Classes\.' + ext, '');

    RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.' + ext + '\UserChoice', 'Progid', str);
    if CompareText(str, argsArray[0]) = 0 then
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.' + ext + '\UserChoice');

    //RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, ExpandConstant('Software\Classes\Applications\{#NAME_EXE_OUT})'));
    RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, ExpandConstant('Software\Classes\.' + ext + '\OpenWithList\{#NAME_EXE_OUT}'));
  end;
#endif

end;

{
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
    MsgBox(MemoDirInfo, mbInformation, MB_OK);
    Result:=MemoUserInfoInfo + NewLine + MemoDirInfo + NewLine + MemoTypeInfo + NewLine + MemoComponentsInfo + NewLine + MemoGroupInfo + NewLine + MemoTasksInfo;
end;
}

procedure UnassociateExtensions;
var
  i: Integer;
  argsArray: TArrayOfString;
  ext, str, prev: string;
  version: TWindowsVersion;
begin
  initExtensions();

  for  i := 0 to GetArrayLength(AudioExts) - 1 do
  begin
    Explode(argsArray, ExtensionRegistryInfo[i],':');
    RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, 'Software\Classes\' + argsArray[0]);

    ext := LowerCase(AudioExts[i]);
    RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext + '\OpenWithProgids', argsArray[0]);
    RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext + '\OpenWithProgids', ExpandConstant('{#ASSOC_PROG_ID}'));

    // the application that opened the type before setup took it over
    str := '';
    RegQueryStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext, '', str);
    if CompareText(str, argsArray[0]) = 0 then begin
      prev := '';
      if RegQueryStringValue(HKEY_LOCAL_MACHINE, '{#APP_REG_PATH}\PreviousAssociations', '.' + ext, prev) and (Length(prev) <> 0) then
        RegWriteStringValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext, '', prev)
      else
        RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\Classes\.' + ext, '');
    end;

    str := '';
    RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Classes\.' + ext, '', str);
    if CompareText(str, argsArray[0]) = 0 then
      RegDeleteValue(HKEY_CURRENT_USER, 'Software\Classes\.' + ext, '');

    str := '';
    RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.' + ext + '\UserChoice', 'Progid', str);
    if CompareText(str, argsArray[0]) = 0 then
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.' + ext + '\UserChoice');

    //RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, ExpandConstant('Software\Classes\Applications\{#NAME_EXE_OUT})'));
    RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, ExpandConstant('Software\Classes\.' + ext + '\OpenWithList\{#NAME_EXE_OUT}'));
  end;

  RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, '{#APP_REG_PATH}\PreviousAssociations');
  RemoveDefaultAssociationsPolicy;

  RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, '{#APP_REG_PATH}\Capabilities');
  RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\RegisteredApplications', '{#ASCC_REG_REGISTERED_APP_NAME}');
  RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, '{#APP_REG_PATH}\Apps');
  RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\RegisteredApplications', 'EuroOffice Writer');
  RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\RegisteredApplications', 'EuroOffice Sheet');
  RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\RegisteredApplications', 'EuroOffice Presentation');
  RegDeleteValue(HKEY_LOCAL_MACHINE, 'Software\RegisteredApplications', 'EuroOffice PDF');
  RegDeleteValue(HKEY_CLASSES_ROOT, 'Local Settings\Software\Microsoft\Windows\Shell\MuiCache', ExpandConstant('{app}\{#iconsExe}'));

  RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, ExpandConstant('Software\Classes\.docx\{#ASCC_REG_PREFIX}.Document.12'));
  RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, ExpandConstant('Software\Classes\.pptx\{#ASCC_REG_PREFIX}.Show.12'));
  RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, ExpandConstant('Software\Classes\.xlsx\{#ASCC_REG_PREFIX}.Sheet.12'));
#ifdef _EuroOffice
  RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, ExpandConstant('Software\Classes\.pdf\{#ASCC_REG_PREFIX}.Pdf'));
#endif
end;

////////////////////
// Uninstall Page //
////////////////////

#ifdef UNINSTALL_USE_CLEAR_PAGE
var
  IsClearData: Boolean;

procedure InitializeUninstallProgressForm();
var
  PageText: TNewStaticText;
  PageNameLabel: string;
  PageDescriptionLabel: string;
  CancelButtonEnabled: Boolean;
  CancelButtonModalResult: Integer;
  CheckBox: TNewCheckBox;
  UninstallFirstPage: TNewNotebookPage;
  UninstallNextButton: TNewButton;
begin
  IsClearData := False;

  if not UninstallSilent then
  begin
    { Create the first page and make it active }
    UninstallFirstPage := TNewNotebookPage.Create(UninstallProgressForm);
    UninstallFirstPage.Notebook := UninstallProgressForm.InnerNotebook;
    UninstallFirstPage.Parent := UninstallProgressForm.InnerNotebook;
    UninstallFirstPage.Align := alClient;

    PageText := TNewStaticText.Create(UninstallProgressForm);
    PageText.Parent := UninstallFirstPage;
    PageText.Top := UninstallProgressForm.StatusLabel.Top;
    PageText.Left := UninstallProgressForm.StatusLabel.Left;
    PageText.Width := UninstallProgressForm.StatusLabel.Width;
    PageText.Height := UninstallProgressForm.StatusLabel.Height;
    PageText.AutoSize := False;
    PageText.ShowAccelChar := False;
    PageText.Caption := ExpandConstant('{cm:UninstallPageLabel}');

    CheckBox := TNewCheckBox.Create(UninstallProgressForm);
    CheckBox.Parent := UninstallFirstPage;
    CheckBox.Top := PageText.Top + PageText.Height + ScaleY(8);
    CheckBox.Left := PageText.Left;
    CheckBox.Width := UninstallProgressForm.Width;
    CheckBox.Height := ScaleY(17);
    CheckBox.Caption := ' ' + ExpandConstant('{cm:UninstallOptionClearData}');

    UninstallProgressForm.InnerNotebook.ActivePage := UninstallFirstPage;

    PageNameLabel := UninstallProgressForm.PageNameLabel.Caption;
    PageDescriptionLabel := UninstallProgressForm.PageDescriptionLabel.Caption;

    { Create the second page }

    UninstallNextButton := TNewButton.Create(UninstallProgressForm);
    UninstallNextButton.Parent := UninstallProgressForm;
    UninstallNextButton.Left := UninstallProgressForm.CancelButton.Left - UninstallProgressForm.CancelButton.Width - ScaleX(10);
    UninstallNextButton.Top := UninstallProgressForm.CancelButton.Top;
    UninstallNextButton.Width := UninstallProgressForm.CancelButton.Width;
    UninstallNextButton.Height := UninstallProgressForm.CancelButton.Height;
    UninstallNextButton.Caption := ExpandConstant('{cm:Uninstall}');
    { Make the "Uninstall" button break the ShowModal loop }
    UninstallNextButton.ModalResult := mrOK;

    UninstallNextButton.TabOrder := UninstallProgressForm.CancelButton.TabOrder;
    UninstallProgressForm.CancelButton.TabOrder := UninstallNextButton.TabOrder + 1;

    { Run our wizard pages }
    //UpdateUninstallWizard;
    CancelButtonEnabled := UninstallProgressForm.CancelButton.Enabled
    UninstallProgressForm.CancelButton.Enabled := True;
    CancelButtonModalResult := UninstallProgressForm.CancelButton.ModalResult;
    UninstallProgressForm.CancelButton.ModalResult := mrCancel;

    if UninstallProgressForm.ShowModal = mrCancel then Abort;

    UninstallNextButton.Enabled := False;
    IsClearData := CheckBox.State = cbChecked;

    { Restore the standard page payout }
    UninstallProgressForm.CancelButton.Enabled := CancelButtonEnabled;
    UninstallProgressForm.CancelButton.ModalResult := CancelButtonModalResult;

    UninstallProgressForm.PageNameLabel.Caption := PageNameLabel;
    UninstallProgressForm.PageDescriptionLabel.Caption := PageDescriptionLabel;

    UninstallProgressForm.InnerNotebook.ActivePage := UninstallProgressForm.InstallingPage;
  end;
end;
#endif

////////////////////
// Common         //
////////////////////

const
  SMTO_ABORTIFHUNG = 2;
  WM_WININICHANGE = $001A;
  WM_SETTINGCHANGE = WM_WININICHANGE;
  WM_USER = $400;

type
  WPARAM = UINT_PTR;
  LPARAM = INT_PTR;
  LRESULT = INT_PTR;

var
  gHWND: Longint;
  isInstalled: Boolean;

procedure GetSystemTimeAsFileTime(var lpFileTime: TFileTime); external 'GetSystemTimeAsFileTime@kernel32.dll';

function GetHKLM: Integer; forward;

function CheckAppRegData(RegName: string; RegData: string): Boolean;
var
  Data: string;
begin
  Result := True;
  if RegQueryStringValue(HKLM, '{#APP_REG_PATH}', RegName, Data) then
    if (Trim(Data) = '') or (CompareText(RegData, Data) <> 0) then
      Result := False;
  // MsgBox(FmtMessage('App Reg: %1 - %2 - %3', [RegData, Data, IntToStr(CompareText(RegData, Data))]), mbInformation, MB_OK);
end;

function CheckUninstalledRegData(RegRoot: integer; RegData: string): Boolean;
var
  Data: string;
begin
  Result := True;
  if RegQueryStringValue(RegRoot,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#APP_REG_UNINST_KEY}_is1',
    'DisplayName', Data) then
    if Pos(RegData, Data) = 0 then
      Result := False;
  // MsgBox(FmtMessage('Uninstalled Reg: %1 - %2 - %3', [RegData, Data, IntToStr(Pos(RegData, Data))]), mbInformation, MB_OK);
end;

function CheckInstalledProduct(): Boolean;
var
  Check: boolean;
begin
  Result := True;
  Check := True;

  Check := Check and CheckAppRegData('PackageType', 'inno');
  Check := Check and not IsMsiProductInstalled('{47EEF706-B0E4-4C43-944B-E5F914B92B79}', 0);
  if Result and not Check then
  begin
    MsgBox(ExpandConstant('{cm:ErrorMismatchInstalledType}'), mbCriticalError, MB_OK);
    Result := False;
  end;

  Check := Check and CheckAppRegData('PackageArch', '{#ARCH}');
  Check := Check and CheckUninstalledRegData(HKLM, '({#ARCH})');
#if ARCH == "x86"
  if IsWin64 and not Is64BitInstallMode then
    Check := Check and CheckUninstalledRegData(HKLM64, '({#ARCH})');
#else
  if IsWin64 and Is64BitInstallMode then
    Check := Check and CheckUninstalledRegData(HKLM32, '({#ARCH})');
#endif
  if Result and not Check then
  begin
    MsgBox(ExpandConstant('{cm:ErrorMismatchInstalledArch}'), mbCriticalError, MB_OK);
    Result := False;
  end;

  Check := Check and CheckAppRegData('PackageEdition', '{#PACKAGE_EDITION}');
  if Result and not Check then
  begin
    MsgBox(ExpandConstant('{cm:ErrorMismatchInstalledEdition}'), mbCriticalError, MB_OK);
    Result := False;
  end;
end;

function SendTextMessageTimeout(hWnd: HWND; Msg: UINT; wParam: WPARAM; lParam: PAnsiChar; fuFlags: UINT; uTimeout: UINT; out lpdwResult: DWORD): LRESULT;
  external 'SendMessageTimeoutA@user32.dll stdcall';

procedure InitializeWizard();
var
  paramSkip: string;
  path: string;
begin
  InitializeAssociatePage();

  if RegQueryStringValue(GetHKLM(), '{#APP_REG_PATH}', 'AppPath', path) and
        FileExists(path + '\{#NAME_EXE_OUT}') then
    isInstalled := false
  else isInstalled := true;
end;

function InitializeSetup(): Boolean;
var
  OutResult: Boolean;
  path, mess: string;
  regkey: integer;

  hWnd: Longint;
  msg: string;
begin
  gHWND := 0;
  OutResult := True;

  if not CheckInstalledProduct() then
  begin
    OutResult := False;
  end;

  if OutResult then begin
    if CheckCommandlineParam('/update') then
    begin
      gHWND := FindWindowByClassName('{#APPWND_CLASS_NAME}');
      if gHWND <> 0 then begin
        OutResult := (IDOK = MsgBox(ExpandConstant('{cm:UpdateAppRunning,{#sAppName}}'), mbInformation, MB_OKCANCEL));
        if OutResult then begin
          PostMessage(gHWND, WM_USER+254, 0, 0);
          Sleep(1000);

          while true do begin
            hWnd := FindWindowByClassName('{#APPWND_CLASS_NAME}');
            if hWnd <> 0 then begin
              msg := FmtMessage(SetupMessage(msgSetupAppRunningError), ['{#sAppName}']);
              if IDCANCEL = MsgBox(msg, mbError, MB_OKCANCEL) then begin
                OutResult := false;
                break;
              end;
            end else
              break;
          end;
        end;
      end;
    end;
  end;

  Result := OutResult;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  regValue, userPath: string;
  findRec: TFindRec;
  ErrorCode: Integer;
  version: TWindowsVersion;
begin
  if CurUninstallStep = usUninstall then
  begin
    GetWindowsVersionEx(version);
    if (version.Major > 6) or ((version.Major = 6) and (version.Minor >= 1)) then begin
      // No --remove-jump-list: this build has no projicons helper, so
      // {#iconsExe} is the editor itself and would open a window and stop
      // the uninstall until someone closed it.
      Exec(ExpandConstant('{app}\updatesvc.exe'), '--delete', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
    end;

    // the file types go back to the applications that had them, before
    // the settings below (which remember those) can be cleared
    UnassociateExtensions();

    RegQueryStringValue(GetHKLM(), ExpandConstant('{#APP_REG_PATH}'), 'uninstall', regValue);

    // User settings and recent documents stay unless the user says to clear
    // them: "No" is the default answer, and a silent uninstall keeps them
    // (/uninst=full at install time clears them without asking). Documents
    // and crash-recovery copies (recover*) are never deleted.
    if (regValue <> 'full') and
#ifndef UNINSTALL_USE_CLEAR_PAGE
        (SuppressibleMsgBox(ExpandConstant('{cm:WarningClearAppData}'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES)
#else
        IsClearData
#endif
            then regValue := 'soft';
    if regValue = 'full' then regValue := 'soft';

    userPath := ExpandConstant('{localappdata}\{#sIntCompanyName}');
    if regValue = 'soft' then begin
      RegDeleteKeyIncludingSubkeys(GetHKLM(), 'Software\{#sIntCompanyName}');
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\{#sIntCompanyName}');

      // remove all app and user cashed data except of folders 'recover' and 'sdkjs-plugins'
      userPath := userPath + '\{#sIntProductName}';
      DelTree(userPath + '\*', False, True, False);

      userPath := userPath + '\data';
      if FindFirst(userPath + '\*', findRec) then begin
        try repeat
            if findRec.Attributes and FILE_ATTRIBUTE_DIRECTORY = 0 then
              DeleteFile(userPath + '\' + findRec.Name)
            else if (findRec.Name <> '.') and (findRec.Name <> '..') and
                (Copy(findRec.Name, 1, 7) <> 'recover') and (findRec.Name <> 'sdkjs-plugins') then begin
              DelTree(userPath + '\' + findRec.Name, True, True, True);
            end;
          until not FindNext(findRec);
        finally
          FindClose(findRec);
        end;
      end;

    end;
  end else
  if CurUninstallStep = usPostUninstall then begin
    RemoveExtraFiles();
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  commonCachePath, userCachePath: string;
  paramStore: string;
  ErrorCode: Integer;
  version: TWindowsVersion;
begin
  if CurStep = ssPostInstall then begin
    DoPostInstall();
    GetWindowsVersionEx(version);
    if (version.Major > 6) or ((version.Major = 6) and (version.Minor >= 1)) then begin
      // No --create-jump-list: {#iconsExe} is the editor itself in this
      // build (no projicons helper); it would open a window and hold setup.
      // Secure Office Suite never checks for updates online and installs no update service.
      RegWriteDWordValue(HKEY_LOCAL_MACHINE, ExpandConstant('{#APP_REG_PATH}'), 'CheckForUpdates', 0);
    end;
    // migrate from the prev version when user's data saved to system common path
    commonCachePath := ExpandConstant('{commonappdata}\{#APP_PATH}\data\cache');
    userCachePath := ExpandConstant('{localappdata}\{#APP_PATH}\data\cache');
    if DirExists(commonCachePath) then begin
      ForceDirectories(userCachePath);
      DirectoryCopy(commonCachePath, userCachePath);
    end;

    paramStore := GetCommandlineParam('/store');
    if Length(paramStore) > 0 then begin
      RegWriteStringValue(HKEY_LOCAL_MACHINE, ExpandConstant('{#APP_REG_PATH}'), 'Store', paramStore);
    end;

    paramStore := GetCommandlineParam('/uninst');
    if (Length(paramStore) > 0) and (paramStore = 'full') then begin
      RegWriteStringValue(HKEY_LOCAL_MACHINE, ExpandConstant('{#APP_REG_PATH}'), 'uninstall', paramStore);
    end;

    if CheckCommandlineParam('/disableplugins') then begin
      if DirExists(ExpandConstant('{app}\editors\sdkjs-plugins\') + '{AA2EA9B6-9EC2-415F-9762-634EE8D9A95E}') then
        DelTree(ExpandConstant('{app}\editors\sdkjs-plugins\') + '{AA2EA9B6-9EC2-415F-9762-634EE8D9A95E}', True, True, True);
    end;

    if CheckCommandlineParam('/noassocheck') then begin
      RegWriteStringValue(HKEY_LOCAL_MACHINE, ExpandConstant('{#APP_REG_PATH}'), 'ignoreAssocMsg', 'true');
    end;

  end else
  if CurStep = ssDone then begin
    // if not (gHWND = 0) then begin
    if CheckCommandlineParam('/update') and not CheckCommandlineParam('/nolaunch') then begin
      ShellExecAsOriginalUser('', ExpandConstant('{app}\{#iconsExe}'), '', '', SW_SHOW, ewNoWait, ErrorCode);
    end
  end else
    WizardForm.CancelButton.Enabled := isInstalled;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  path: string;
  ErrorCode: integer;
  version: TWindowsVersion;
begin
  GetWindowsVersionEx(version);
  if (version.Major > 6) or ((version.Major = 6) and (version.Minor >= 1)) then begin
    if FileExists(ExpandConstant('{app}\updatesvc.exe')) then
      Exec(ExpandConstant('{app}\updatesvc.exe'), '--delete', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  end;

  path := ExpandConstant('{app}\editors\web-apps');
  if DirExists(path) then DelTree(path, true, true, true);

  path := ExpandConstant('{app}\editors\sdkjs');
  if DirExists(path) then DelTree(path, true, true, true)
end;

#ifndef _WIN_XP
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpSelectDir) and not CheckCommandlineParam('/enabledirpage');
end;
#endif

function getAppMutex(P: String): String;
var
  hWnd: Longint;
begin
  if not CheckCommandlineParam('/update') then
    // the suite page and each of the four applications (cappidentity.cpp)
    Result := '{#APP_MUTEX_NAME},{#APP_MUTEX_NAME}.writer,{#APP_MUTEX_NAME}.sheet,{#APP_MUTEX_NAME}.presentation,{#APP_MUTEX_NAME}.pdf'
  else
    Result := 'UPDATE';
end;

procedure installVCRedist(FileName, LabelCaption: String);
var
  Params:    String;
  ErrorCode: Integer;
begin
  if Length(LabelCaption) > 0 then WizardForm.StatusLabel.Caption := LabelCaption;

  Params := '/quiet /norestart';

  ShellExec('', FileName, Params, '', SW_SHOW, ewWaitUntilTerminated, ErrorCode);

  WizardForm.StatusLabel.Caption := SetupMessage(msgStatusExtractFiles);
end;

function GetHKLM: Integer;
begin
  if IsWin64 then
    Result := HKLM64
  else
    Result := HKEY_LOCAL_MACHINE;
end;

function getPosixTime: string;
var
  fileTime: TFileTime;
  fileTimeNano100: Int64;
begin
  //GetSystemTime(systemTime);

  // the current file time
  //SystemTimeToFileTime(systemTime, fileTime);
  GetSystemTimeAsFileTime(fileTime);

  // filetime in 100 nanosecond resolution
  fileTimeNano100 := Int64(fileTime.dwHighDateTime) shl 32 + fileTime.dwLowDateTime;

  //Log('The Value is: ' + IntToStr(fileTimeNano100/10000 - 11644473600000));

  //to milliseconds and unix windows epoche offset removed
  Result := IntToStr(fileTimeNano100/10000 - 11644473600000);
end;

function getAppPrevLang(param: string): string;
var
  lang: string;
begin
  if not (WizardSilent() and
        RegValueExists(GetHKLM(), '{#APP_REG_PATH}', 'locale') and
            RegQueryStringValue(GetHKLM(), '{#APP_REG_PATH}', 'locale', lang)) then
  begin
    lang := ExpandConstant('{cm:AppLocale}')
  end;

  result := lang;
end;

function libExists(const dllname: String) : boolean;
begin
  Result := not FileExists(ExpandConstant('{sys}\'+dllname));
end;

function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(GetHKLM(), 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', OrigPath)
  then begin
    Result := True;
    Result := True;
    exit;
  end;
  // look for the path with leading and trailing semicolon
  // Pos() returns 0 if not found
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;

procedure RefreshEnvironment;
var
  S: AnsiString;
  MsgResult: DWORD;
begin
  S := 'Environment';
  SendTextMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, PAnsiChar(S), SMTO_ABORTIFHUNG, 5000, MsgResult);
end;
