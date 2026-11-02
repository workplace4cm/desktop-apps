<#
.SYNOPSIS
    Secure Office Suite: Windows integration of EuroOffice Writer, Sheet,
    Presentation and PDF, checked with the real installer.

.DESCRIPTION
    verify_windows.ps1 -Installer <setup.exe> -Out <dir>

    Installs silently (with /FULLASSOCIATION, as an administrator deploying
    the suite would), then checks:
      1. four Start Menu entries and four desktop shortcuts, each starting its
         own application with its own icon, and no suite entry;
      2. Default Apps lists the four applications with their file types;
      3. each file type's open command (as Explorer resolves it, user choice
         included) is its application, and the default associations file and
         policy name it;
      4. opening a document of each type the way a double-click does
         (ShellExecute) opens that very document in the right application;
      5. installing again (an upgrade) keeps settings, recent documents,
         recovery copies and documents, and the file types;
      6. a silent uninstall removes shortcuts, file types and policy, puts
         back the applications the types had before, and keeps user data
         and documents.
    Needs an interactive desktop session (GitHub's Windows runners have one)
    and administrator rights.
#>
param(
    [Parameter(Mandatory)] [string]$Installer,
    [Parameter(Mandatory)] [string]$Out
)

$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Installer = (Resolve-Path $Installer).Path
$Samples = Join-Path $PSScriptRoot 'samples'
$script:Fails = 0

function Pass([string]$m) { Write-Host "PASS: $m" }
function Fail([string]$m) { Write-Host "FAIL: $m"; $script:Fails++ }

Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class SosWin {
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("shlwapi.dll", CharSet = CharSet.Unicode)]
    static extern int AssocQueryString(int flags, int str, string assoc, string extra, StringBuilder outStr, ref uint outLen);
    [DllImport("shell32.dll")] public static extern void SHChangeNotify(int e, int f, IntPtr a, IntPtr b);

    // visible top-level windows: "pid<TAB>title"
    public static List<string> Windows() {
        var r = new List<string>();
        EnumWindows(delegate (IntPtr h, IntPtr l) {
            if (IsWindowVisible(h)) {
                var sb = new StringBuilder(1024);
                GetWindowText(h, sb, 1024);
                if (sb.Length > 0) { uint pid; GetWindowThreadProcessId(h, out pid); r.Add(pid + "\t" + sb.ToString()); }
            }
            return true;
        }, IntPtr.Zero);
        return r;
    }

    // what Explorer runs for a file type (ASSOCSTR_COMMAND = 1, ASSOCSTR_PROGID = 20)
    public static string Assoc(string ext, int what) {
        uint n = 2048; var sb = new StringBuilder(2048);
        int hr = AssocQueryString(0, what, ext, what == 1 ? "open" : null, sb, ref n);
        return hr == 0 ? sb.ToString() : "";
    }
}
"@

$Apps = [ordered]@{ writer = 'EuroOffice Writer'; sheet = 'EuroOffice Sheet'; presentation = 'EuroOffice Presentation'; pdf = 'EuroOffice PDF' }
function Owner([string]$ext) {
    switch ($ext.TrimStart('.').ToLower()) {
        { $_ -in 'doc','docx','odt','rtf','txt' } { 'writer' }
        { $_ -in 'xls','xlsx','ods','csv' }      { 'sheet' }
        { $_ -in 'ppt','pptx','odp' }            { 'presentation' }
        'pdf'                                    { 'pdf' }
    }
}
$Exts = Get-ChildItem $Samples -Filter 'Sample.*' | Where-Object Extension -ne '.md' | ForEach-Object { $_.Extension.ToLower() }

$RegApp = 'HKLM:\SOFTWARE\Secure Office Suite\DesktopEditors'
$PolicyKey = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\System'
$UserData = Join-Path $env:LOCALAPPDATA 'Secure Office Suite'
$UserReg = 'HKCU:\Software\Secure Office Suite\DesktopEditors'
$Docs = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'sos-integration'

function AppCommandLine([int]$procId) {
    (Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue).CommandLine
}
function AppOf([int]$procId) {
    $cl = AppCommandLine $procId
    if ($cl -match '--app=(\w+)') { $Matches[1] } else { '' }
}

# first window whose title matches $re: @{pid; title}, or $null after $secs
function Wait-Window([string]$re, [int]$secs = 150) {
    for ($i = 0; $i -lt $secs; $i++) {
        foreach ($w in [SosWin]::Windows()) {
            $p, $t = $w -split "`t", 2
            if ($t -match $re) { return @{ pid = [int]$p; title = $t } }
        }
        Start-Sleep -Seconds 1
    }
    return $null
}
function Show-Windows {
    [SosWin]::Windows() | Where-Object { $_ -match 'EuroOffice|Secure Office' } | ForEach-Object { Write-Host "    window: $_" }
}
# why an application is gone: its processes and Windows' crash reports
function Show-Crashes {
    Get-CimInstance Win32_Process -Filter "Name='DesktopEditors.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -notmatch '--type=' } |
        ForEach-Object { Write-Host "    process: $($_.ProcessId) $($_.CommandLine)" }
    Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000, 1001, 1002; StartTime = (Get-Date).AddMinutes(-15) } -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match 'DesktopEditors|editors_helper' } | Select-Object -First 4 |
        ForEach-Object { Write-Host "    event $($_.Id) $($_.TimeCreated): $(($_.Message -split "`n" | Select-Object -First 8) -join ' | ')" }
}
function Close-Apps {
    Get-Process DesktopEditors, editors -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 30 -and (Get-Process DesktopEditors, editors -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
    Start-Sleep 2
}
function Save-Screen([string]$name) {
    try {
        Add-Type -AssemblyName System.Windows.Forms, System.Drawing
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
        $bmp.Save((Join-Path $Out "$name.png"))
        $g.Dispose(); $bmp.Dispose()
    } catch { Write-Host "screenshot failed: $_" }
}

# Waits for that process only: Start-Process -Wait would also wait for every
# process it started (an application the installer leaves running).
function Wait-Setup($p, [string]$log, [int]$mins = 15) {
    if (-not $p.WaitForExit($mins * 60 * 1000)) {
        Fail "$($p.ProcessName) still running after $mins minutes"
        $l = Join-Path $Out $log
        if (Test-Path $l) { Get-Content $l -Tail 40 | ForEach-Object { Write-Host "    log: $_" } }
        Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'setup|unins|vc_redist|DesktopEditors|editors|mshta|msiexec|\.tmp' } |
            ForEach-Object { Write-Host "    process: $($_.ProcessId) $($_.CommandLine)" }
        Save-Screen "stuck-$log"
        $p | Stop-Process -Force -ErrorAction SilentlyContinue
        return -1
    }
    return $p.ExitCode
}

function Install([string]$log) {
    Write-Host "installing ($log)"
    $p = Start-Process $Installer -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/FULLASSOCIATION', "/LOG=`"$(Join-Path $Out $log)`"" -PassThru
    return (Wait-Setup $p $log)
}

function Expect-Document([string]$file, [string]$how) {
    $app = Owner ([IO.Path]::GetExtension($file))
    $name = $Apps[$app]
    $re = '^\*?' + [regex]::Escape([IO.Path]::GetFileName($file)) + '( .*)? - ' + [regex]::Escape($name) + '$'
    $w = Wait-Window $re 150
    if ($w) {
        $got = AppOf $w.pid
        if ($got -eq $app) { Pass "$([IO.Path]::GetFileName($file)) ($how) opened in $name (pid $($w.pid))" }
        else { Fail "$([IO.Path]::GetFileName($file)) ($how) window '$($w.title)' is in pid $($w.pid): $(AppCommandLine $w.pid)" }
    } else {
        Fail "$([IO.Path]::GetFileName($file)) ($how) did not open in $name"
        Show-Windows
        Show-Crashes
    }
}

function Check-FileTypes([string]$when) {
    foreach ($ext in $Exts) {
        $app = Owner $ext
        $progId = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$ext" -ErrorAction SilentlyContinue).'(default)'
        $cmd = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$progId\shell\open\command" -ErrorAction SilentlyContinue).'(default)'
        if ($progId -like 'ASC.*' -and $cmd -match "--app=$app ") { Pass "$ext -> $progId -> --app=$app ($when)" }
        else { Fail "$ext -> '$progId' -> '$cmd' ($when)" }
        $resolved = [SosWin]::Assoc($ext, 1)
        if ($resolved -match "DesktopEditors\.exe`"? --app=$app ") { Pass "Explorer opens $ext with --app=$app ($when)" }
        elseif (Guarded $ext) {
            Write-Host "NOTE: Windows kept Edge ($(UserChoiceOf $ext)) as this user's $ext application, so setup cannot change it for the signed-in session; the default associations policy gives $ext to $($Apps[$app]) at the next sign-in ($when)"
            Get-ChildItem $Out -Filter *.log | Select-String -SimpleMatch "for $ext" | ForEach-Object { Write-Host "    log: $($_.Filename): $($_.Line)" }
        }
        else {
            Fail "Explorer opens $ext with '$resolved' (UserChoice: $(UserChoiceOf $ext)) ($when)"
            $uc = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext"
            Get-ChildItem $uc -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    key: $($_.Name) $((Get-ItemProperty $_.PSPath | Out-String).Trim() -replace '\s+', ' ')" }
            (Get-Acl "$uc\UserChoice" -ErrorAction SilentlyContinue).Access | ForEach-Object { Write-Host "    acl: $($_.AccessControlType) $($_.IdentityReference) $($_.RegistryRights)" }
            Write-Host "    UCPD: $((Get-Service UCPD -ErrorAction SilentlyContinue).Status)"
            Get-ChildItem $Out -Filter *.log | Select-String -SimpleMatch "for $ext" | ForEach-Object { Write-Host "    log: $($_.Filename): $($_.Line)" }
        }
    }
}

function UserChoiceOf([string]$ext) {
    (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\UserChoice" -ErrorAction SilentlyContinue).ProgId
}
# Windows keeps Edge as the signed-in user's PDF application: setup clears the
# choice (its log says so) and Windows writes Edge's back straight away (the
# UCPD driver does the same on newer Windows). Only the user, or the default
# associations policy when the user next signs in, can change it.
function Guarded([string]$ext) {
    $uc = UserChoiceOf $ext
    return ($ext -eq '.pdf' -and $uc -like 'MSEdge*')
}

# user files that must survive, with hashes (browser caches excluded)
function Snapshot {
    $files = @()
    if (Test-Path $UserData) {
        $files += Get-ChildItem $UserData -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\cache[^\\]*\\|\\webdata\\|LOCK$|\.lock$|\.log$' }
    }
    $files += Get-ChildItem $Docs -File
    $files | Sort-Object FullName | ForEach-Object { "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash)  $($_.FullName)" }
}

# ---------------------------------------------------------------- install
$before = @{}
foreach ($ext in $Exts) { $before[$ext] = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$ext" -ErrorAction SilentlyContinue).'(default)' }
$before.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" } | Set-Content (Join-Path $Out 'types-before.txt')

$code = Install 'install.log'
if ($code -eq 0) { Pass "installed silently" } else { Fail "installer exit code $code" }
$AppDir = (Get-ItemProperty $RegApp -ErrorAction SilentlyContinue).AppPath
if (-not $AppDir) { Fail "no AppPath in $RegApp"; exit 1 }
Write-Host "installed in $AppDir"
Close-Apps

# ---------------------------------------------------------- 1. shortcuts
Write-Host "== Start Menu and desktop"
$shell = New-Object -ComObject WScript.Shell
$startMenu = [Environment]::GetFolderPath('CommonPrograms')
$desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
foreach ($where in @(@{ dir = $startMenu; what = 'Start Menu entry' }, @{ dir = $desktop; what = 'desktop shortcut' })) {
    $ours = Get-ChildItem $where.dir -Filter '*.lnk' | Where-Object { $_.BaseName -match 'EuroOffice|Secure Office' }
    $names = ($ours.BaseName | Sort-Object) -join ', '
    if ($names -eq (($Apps.Values | Sort-Object) -join ', ')) { Pass "$($where.what)s: $names" } else { Fail "$($where.what)s: $names" }
    foreach ($app in $Apps.Keys) {
        $lnk = Join-Path $where.dir "$($Apps[$app]).lnk"
        if (-not (Test-Path $lnk)) { Fail "no $($where.what) $lnk"; continue }
        $s = $shell.CreateShortcut($lnk)
        $icon = ($s.IconLocation -split ',')[0]
        if ($s.TargetPath -like '*\DesktopEditors.exe' -and $s.Arguments -eq "--app=$app" -and $icon -like "*\icons\$app.ico" -and (Test-Path $icon)) {
            Pass "$($where.what) $($Apps[$app]): $($s.TargetPath) $($s.Arguments), icon $icon"
        } else { Fail "$($where.what) $($Apps[$app]): '$($s.TargetPath)' '$($s.Arguments)' icon '$($s.IconLocation)'" }
    }
}
if (Test-Path (Join-Path $startMenu 'Secure Office Suite')) { Fail "the old Start Menu folder is still there" } else { Pass "no suite folder in the Start Menu" }
$hashes = $Apps.Keys | ForEach-Object { (Get-FileHash (Join-Path $AppDir "icons\$_.ico")).Hash } | Sort-Object -Unique
if (@($hashes).Count -eq 4) { Pass "four different application icons" } else { Fail "application icons are not all different" }

foreach ($app in $Apps.Keys) {
    Start-Process (Join-Path $startMenu "$($Apps[$app]).lnk")
    $w = Wait-Window ('^' + [regex]::Escape($Apps[$app]) + '$') 150
    if ($w -and (AppOf $w.pid) -eq $app) { Pass "the $($Apps[$app]) Start Menu entry starts $($Apps[$app]) (pid $($w.pid))" }
    elseif ($w) { Fail "the $($Apps[$app]) Start Menu entry started $(AppCommandLine $w.pid)" }
    else { Fail "the $($Apps[$app]) Start Menu entry did not start $($Apps[$app])"; Show-Windows }
}
Save-Screen '1-start-menu-launch'
Close-Apps
Start-Process (Join-Path $desktop 'EuroOffice PDF.lnk')
$w = Wait-Window '^EuroOffice PDF$' 150
if ($w -and (AppOf $w.pid) -eq 'pdf') { Pass "the EuroOffice PDF desktop shortcut starts EuroOffice PDF" } else { Fail "the EuroOffice PDF desktop shortcut did not start it" }
Close-Apps

# ------------------------------------------------------- 2. Default Apps
Write-Host "== Default Apps"
$registered = Get-ItemProperty 'HKLM:\SOFTWARE\RegisteredApplications'
foreach ($app in $Apps.Keys) {
    $cap = $registered.($Apps[$app])
    if (-not $cap) { Fail "$($Apps[$app]) is not in Default Apps"; continue }
    $types = (Get-Item "HKLM:\$cap\FileAssociations" -ErrorAction SilentlyContinue).Property
    $want = $Exts | Where-Object { (Owner $_) -eq $app }
    $missing = $want | Where-Object { $_ -notin $types }
    if (-not $missing) { Pass "$($Apps[$app]) is in Default Apps with $($want -join ' ')" } else { Fail "$($Apps[$app]) in Default Apps lacks $($missing -join ' ')" }
}

# ------------------------------------------------------- 3. file types
Write-Host "== file types"
Check-FileTypes 'after install'
$xml = Join-Path $AppDir 'DefaultAssociations.xml'
$policy = (Get-ItemProperty $PolicyKey -ErrorAction SilentlyContinue).DefaultAssociationsConfiguration
if ($policy -eq $xml -and (Test-Path $xml)) { Pass "the default associations policy names $xml" } else { Fail "default associations policy: '$policy'" }
if (Test-Path $xml) {
    Copy-Item $xml $Out
    [xml]$doc = Get-Content $xml
    foreach ($ext in $Exts) {
        $a = $doc.DefaultAssociations.Association | Where-Object Identifier -eq $ext
        if ($a -and $a.ApplicationName -eq $Apps[(Owner $ext)]) { Pass "$xml gives $ext to $($a.ApplicationName) ($($a.ProgId))" } else { Fail "${xml}: $ext -> '$($a.ApplicationName)'" }
    }
}

# ------------------------------------------------------- 4. double-click
Write-Host "== double-click"
New-Item -ItemType Directory -Force -Path $Docs | Out-Null
Copy-Item (Join-Path $Samples 'Sample.*') $Docs -Exclude '*.md'
foreach ($ext in $Exts) {
    $f = Join-Path $Docs "Sample$ext"
    if (Guarded $ext) {
        # what a double-click runs once the policy has applied: our ProgID's open command
        $progId = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$ext").'(default)'
        $cmd = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$progId\shell\open\command").'(default)'
        $exe, $rest = $cmd -split '(?<=^"[^"]+")\s+', 2
        Start-Process -FilePath $exe.Trim('"') -ArgumentList ($rest -replace '%1', $f)
        Expect-Document $f "open command of $progId"
    } else {
        Start-Process -FilePath $f
        Expect-Document $f 'double-click'
        if ($ext -eq '.csv') {
            # CSV asks for its import options first; the application must stay up meanwhile
            $w = Wait-Window ('^\*?Sample\.csv( .*)? - ' + [regex]::Escape($Apps.sheet) + '$') 5
            Start-Sleep 12
            if ($w -and (Get-Process -Id $w.pid -ErrorAction SilentlyContinue)) { Pass "EuroOffice Sheet still running 12 s after opening Sample.csv (pid $($w.pid))" }
            else { Fail "EuroOffice Sheet (pid $($w.pid)) quit within 12 s of opening Sample.csv"; Show-Windows; Show-Crashes }
        }
    }
}
Save-Screen '4-double-click'
[SosWin]::Windows() | Set-Content (Join-Path $Out 'windows-double-click.txt')
foreach ($app in $Apps.Keys) {
    $n = @(Get-CimInstance Win32_Process -Filter "Name='DesktopEditors.exe'" | Where-Object { $_.CommandLine -match "--app=$app( |$)" -and $_.CommandLine -notmatch '--type=' }).Count
    if ($n -eq 1) { Pass "one $app process for all its documents" } else { Write-Host "note: $n $app processes" }
}
Close-Apps

# ---------------------------------------------------------- 5. upgrade
Write-Host "== upgrade"
New-Item -ItemType Directory -Force -Path (Join-Path $UserData 'DesktopEditors') | Out-Null
Set-Content (Join-Path $UserData 'DesktopEditors\sos-integration-marker.txt') "user data $(Get-Date)"
New-Item -Force -Path $UserReg -ErrorAction SilentlyContinue | Out-Null
Set-ItemProperty $UserReg -Name SosIntegrationMarker -Value 'keep me'
Set-ItemProperty $UserReg -Name locale -Value 'de-DE'   # the user picked another language
$regBefore = (Get-ItemProperty $UserReg | Out-String)
$snap = Snapshot
$snap | Set-Content (Join-Path $Out 'user-files-before.txt')
Write-Host "user files: $(@($snap).Count)"
Get-ChildItem $UserData -Recurse -Directory -ErrorAction SilentlyContinue | ForEach-Object FullName | Set-Content (Join-Path $Out 'user-folders.txt')
if ($snap -match 'recents\.xml') { Pass "recent documents were recorded" } else { Write-Host "note: no recents.xml yet" }

$code = Install 'upgrade.log'
if ($code -eq 0) { Pass "installed again over the installed version" } else { Fail "upgrade exit code $code" }
Close-Apps
$after = Snapshot
$diff = Compare-Object @($snap) @($after)
if (-not $diff) { Pass "the upgrade kept every settings, recents, recovery and document file unchanged" }
else { Fail "user files changed in the upgrade:"; $diff | Format-Table -AutoSize | Out-String | Write-Host }
$regAfter = (Get-ItemProperty $UserReg -ErrorAction SilentlyContinue | Out-String)
if ($regAfter -eq $regBefore) { Pass "the upgrade kept the user's settings in the registry" }
else {
    Fail "user registry settings changed in the upgrade"
    Compare-Object ($regBefore -split "`r?`n") ($regAfter -split "`r?`n") | ForEach-Object { Write-Host "    $($_.SideIndicator) $($_.InputObject)" }
}
Check-FileTypes 'after upgrade'
Start-Process -FilePath (Join-Path $Docs 'Sample.xlsx')
Expect-Document (Join-Path $Docs 'Sample.xlsx') 'double-click after upgrade'
Close-Apps

# -------------------------------------------------------- 6. uninstall
Write-Host "== uninstall"
$snap = Snapshot | Where-Object { $_ -notmatch 'recents\.xml' }
$uninstaller = Join-Path $AppDir 'unins000.exe'
$p = Start-Process $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$(Join-Path $Out 'uninstall.log')`"" -PassThru
Wait-Setup $p 'uninstall.log' | Out-Null
# the uninstaller hands over to a copy of itself and returns at once
for ($i = 0; $i -lt 300 -and (Test-Path $uninstaller); $i++) { Start-Sleep 1 }
Start-Sleep 5
if (Test-Path (Join-Path $AppDir 'DesktopEditors.exe')) { Fail "the program files are still there" } else { Pass "uninstalled" }
foreach ($dir in @($startMenu, $desktop)) {
    $left = Get-ChildItem $dir -Filter '*.lnk' | Where-Object { $_.BaseName -match 'EuroOffice|Secure Office' }
    if ($left) { Fail "shortcuts left in ${dir}: $($left.Name -join ', ')" } else { Pass "no shortcuts left in $dir" }
}
foreach ($ext in $Exts) {
    $now = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$ext" -ErrorAction SilentlyContinue).'(default)'
    if ($now -like 'ASC.*') { Fail "$ext still opens with $now" }
    elseif ($now -eq $before[$ext]) { Pass "$ext is back to '$now'" }
    else { Fail "$ext is '$now', was '$($before[$ext])' before installing" }
}
if (Test-Path 'HKLM:\SOFTWARE\Classes\ASC.Document.12') { Fail "ProgIDs left behind" } else { Pass "ProgIDs removed" }
if ((Get-ItemProperty $PolicyKey -ErrorAction SilentlyContinue).DefaultAssociationsConfiguration) { Fail "the default associations policy is still set" } else { Pass "the default associations policy removed" }
$registered = Get-ItemProperty 'HKLM:\SOFTWARE\RegisteredApplications'
if ($Apps.Values | Where-Object { $registered.$_ }) { Fail "applications still in Default Apps" } else { Pass "applications removed from Default Apps" }
$after = Snapshot | Where-Object { $_ -notmatch 'recents\.xml' }
$diff = Compare-Object @($snap) @($after)
if (-not $diff) { Pass "the uninstall kept settings, recovery copies and documents" }
else { Fail "user files changed in the uninstall:"; $diff | Format-Table -AutoSize | Out-String | Write-Host }
if ((Get-ItemProperty $UserReg -ErrorAction SilentlyContinue).SosIntegrationMarker -eq 'keep me') { Pass "the uninstall kept the user's settings in the registry" } else { Fail "the uninstall removed the user's registry settings" }

Write-Host "failures: $script:Fails"
exit ([int]($script:Fails -gt 0))
