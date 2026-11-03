<#
.SYNOPSIS
    Secure Office Suite: Windows release checks that the build's own check
    (verify_windows.ps1) doesn't make.

.DESCRIPTION
    verify_release_windows.ps1 -Installer <new setup.exe> [-Previous <earlier setup.exe>] -Out <dir>

    With no network for the installer and the applications (outbound
    firewall rules block them, and a watcher records every connection they
    try), checks:
      1. the machine is clean: the suite is not installed;
      2. clean install of the new build, or of the earlier one first when
         -Previous is given so that the new one is a real upgrade;
      3. each application opens a document of its own, so the user has
         documents, recent documents, settings and profiles;
      4. the upgrade keeps every user file and the user's settings, and the
         recent documents are still listed after the applications restart;
      5. uninstall keeps user data; installing again brings back the Start
         Menu entries, desktop shortcuts and file types, and the
         applications start with the user's recent documents;
      6. EuroOffice Sheet stays up after a CSV double-click, six times, three
         of them on a brand-new user profile (the Phase 9 medium finding);
      7. neither the installer nor the applications tried to reach the
         network.
    Needs an interactive desktop session and administrator rights.
#>
param(
    [Parameter(Mandatory)] [string]$Installer,
    [string]$Previous = '',
    [Parameter(Mandatory)] [string]$Out
)

$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Installer = (Resolve-Path $Installer).Path
if ($Previous) { $Previous = (Resolve-Path $Previous).Path }
$Samples = Join-Path $PSScriptRoot 'samples'
$script:Fails = 0
function Pass([string]$m) { Write-Host "PASS: $m" }
function Fail([string]$m) { Write-Host "FAIL: $m"; $script:Fails++ }

Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class SosRel {
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
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
}
"@

$Apps = [ordered]@{ writer = 'EuroOffice Writer'; sheet = 'EuroOffice Sheet'; presentation = 'EuroOffice Presentation'; pdf = 'EuroOffice PDF' }
$SampleOf = @{ writer = 'Sample.docx'; sheet = 'Sample.xlsx'; presentation = 'Sample.pptx'; pdf = 'Sample.pdf' }
$RegApp = 'HKLM:\SOFTWARE\Secure Office Suite\DesktopEditors'
$AppDir = Join-Path $env:ProgramFiles 'Secure Office Suite\DesktopEditors'
$Exe = Join-Path $AppDir 'DesktopEditors.exe'
$UserData = Join-Path $env:LOCALAPPDATA 'Secure Office Suite'
$UserReg = 'HKCU:\Software\Secure Office Suite\DesktopEditors'
$Docs = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'sos-release'
$StartMenu = [Environment]::GetFolderPath('CommonPrograms')
$Desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')

function AppOf([int]$procId) {
    $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue).CommandLine
    if ($cl -match '--app=(\w+)') { $Matches[1] } else { '' }
}
function Wait-Window([string]$re, [int]$secs = 150) {
    for ($i = 0; $i -lt $secs; $i++) {
        foreach ($w in [SosRel]::Windows()) {
            $p, $t = $w -split "`t", 2
            if ($t -match $re) { return @{ pid = [int]$p; title = $t } }
        }
        Start-Sleep -Seconds 1
    }
    return $null
}
function Show-Windows {
    [SosRel]::Windows() | Where-Object { $_ -match 'EuroOffice|Secure Office|Sample' } | ForEach-Object { Write-Host "    window: $_" }
}
function Show-Crashes {
    Get-CimInstance Win32_Process -Filter "Name='DesktopEditors.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -notmatch '--type=' } | ForEach-Object { Write-Host "    process: $($_.ProcessId) $($_.CommandLine)" }
    Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000, 1001, 1002; StartTime = (Get-Date).AddMinutes(-5) } -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match 'DesktopEditors|editors_helper' } | Select-Object -First 4 |
        ForEach-Object { Write-Host "    event $($_.Id) $($_.TimeCreated): $(($_.Message -split "`n" | Select-Object -First 8) -join ' | ')" }
}
function Close-Apps {
    Get-Process DesktopEditors, editors, editors_helper -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
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
function Run-Setup([string]$file, [string]$log) {
    Write-Host "running $([IO.Path]::GetFileName($file)) ($log)"
    $p = Start-Process $file -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/FULLASSOCIATION', "/LOG=`"$(Join-Path $Out $log)`"" -PassThru
    if (-not $p.WaitForExit(15 * 60 * 1000)) { $p | Stop-Process -Force; return -1 }
    return $p.ExitCode
}
function Uninstall([string]$log) {
    $unins = Join-Path $AppDir 'unins000.exe'
    $p = Start-Process $unins -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$(Join-Path $Out $log)`"" -PassThru
    $p.WaitForExit(15 * 60 * 1000) | Out-Null
    for ($i = 0; $i -lt 300 -and (Test-Path $unins); $i++) { Start-Sleep 1 }
    Start-Sleep 5
}

# open the application's sample document as its shortcut would
function Open-Document([string]$app, [string]$when) {
    $f = Join-Path $Docs $SampleOf[$app]
    Start-Process -FilePath $Exe -ArgumentList "--app=$app", "`"$f`""
    $re = '^\*?' + [regex]::Escape($SampleOf[$app]) + '( .*)? - ' + [regex]::Escape($Apps[$app]) + '$'
    $w = Wait-Window $re 150
    if ($w -and (AppOf $w.pid) -eq $app) { Pass "$($Apps[$app]) opened $($SampleOf[$app]) ($when, pid $($w.pid))" }
    elseif ($w) { Fail "$($SampleOf[$app]) opened in pid $($w.pid) ($(AppOf $w.pid)) ($when)" }
    else { Fail "$($Apps[$app]) did not open $($SampleOf[$app]) ($when)"; Show-Windows; Show-Crashes }
}
function Start-FromStartMenu([string]$app, [string]$when) {
    $lnk = Join-Path $StartMenu "$($Apps[$app]).lnk"
    if (-not (Test-Path $lnk)) { Fail "no Start Menu entry $lnk ($when)"; return }
    Start-Process $lnk
    $w = Wait-Window ('^' + [regex]::Escape($Apps[$app]) + '$') 150
    if ($w -and (AppOf $w.pid) -eq $app) { Pass "the $($Apps[$app]) Start Menu entry starts it ($when)" }
    else { Fail "the $($Apps[$app]) Start Menu entry did not start it ($when)"; Show-Windows }
}
function RecentsFile {
    foreach ($c in @((Join-Path $UserData 'DesktopEditors\data\sos-recents.json'), (Join-Path $UserData 'DesktopEditors\sos-recents.json'))) {
        if (Test-Path $c) { return $c }
    }
    return $null
}
function In-Recents([string]$app) {
    $file = RecentsFile
    if (-not $file) { return $false }
    $text = Get-Content $file -Raw -ErrorAction SilentlyContinue
    if (-not $text) { return $false }
    $p = (Join-Path $Docs $SampleOf[$app]) -replace '\\', '/'
    # paths are JSON strings: C:\\Users\\... or C:/Users/...
    return ($text -replace '\\\\', '/' -replace '\\', '/').ToLower().Contains($p.ToLower())
}
# An application records a document once the editor has loaded it, a little
# after its window title shows the name. Give each one up to 60 s before the
# applications are closed, as a user would.
function Wait-Recents {
    foreach ($app in $Apps.Keys) {
        for ($i = 0; $i -lt 60 -and -not (In-Recents $app); $i++) { Start-Sleep 1 }
    }
}
function Check-Recents([string]$when) {
    $file = RecentsFile
    if (-not $file) { Fail "no sos-recents.json ($when)"; return }
    foreach ($app in $Apps.Keys) {
        $found = In-Recents $app
        if ($found) { Pass "$($SampleOf[$app]) is in the $app recent documents ($when)" } else { Fail "$($SampleOf[$app]) is not in the $app recent documents ($when)" }
    }
}
function Snapshot {
    $files = @()
    if (Test-Path $UserData) {
        $files += Get-ChildItem $UserData -Recurse -File -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\cache[^\\]*\\|\\webdata\\|LOCK$|\.lock$|\.log$|\.bak$' }
    }
    $files += Get-ChildItem $Docs -File
    $files | Sort-Object FullName | ForEach-Object { "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash)  $($_.FullName)" }
}
function Check-Installed([string]$when) {
    foreach ($dir in @($StartMenu, $Desktop)) {
        $names = (Get-ChildItem $dir -Filter '*.lnk' | Where-Object { $_.BaseName -match 'EuroOffice|Secure Office' }).BaseName | Sort-Object
        if (($names -join ', ') -eq (($Apps.Values | Sort-Object) -join ', ')) { Pass "four shortcuts in $dir ($when)" } else { Fail "shortcuts in ${dir}: $($names -join ', ') ($when)" }
    }
    foreach ($pair in @(@('.docx', 'writer'), @('.xlsx', 'sheet'), @('.csv', 'sheet'), @('.pptx', 'presentation'), @('.pdf', 'pdf'))) {
        $progId = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$($pair[0])" -ErrorAction SilentlyContinue).'(default)'
        $cmd = (Get-ItemProperty "HKLM:\SOFTWARE\Classes\$progId\shell\open\command" -ErrorAction SilentlyContinue).'(default)'
        if ($cmd -match "--app=$($pair[1]) ") { Pass "$($pair[0]) opens with $($Apps[$pair[1]]) ($when)" } else { Fail "$($pair[0]) -> '$progId' '$cmd' ($when)" }
    }
}

# --------------------------------------------- offline: block and watch
Write-Host "== offline"
$blocked = @($Installer) + $(if ($Previous) { @($Previous) } else { @() }) +
           @('DesktopEditors.exe', 'editors_helper.exe', 'editors.exe', 'converter\x2t.exe', 'unins000.exe' | ForEach-Object { Join-Path $AppDir $_ })
foreach ($prog in $blocked) {
    New-NetFirewallRule -DisplayName "SOS release offline $([IO.Path]::GetFileName($prog))" -Direction Outbound -Program $prog -Action Block | Out-Null
}
Pass "outbound network blocked for the setup programs and the applications (the setup's temporary helper is watched)"
$watchLog = Join-Path $Out 'connections.txt'
$watcher = Start-Job -ArgumentList $AppDir, $Installer, $Previous, $watchLog -ScriptBlock {
    param($appDir, $inst, $prev, $log)
    $seen = @{}
    while ($true) {
        $procs = @{}
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.ExecutablePath -and ($_.ExecutablePath -like "$appDir\*" -or $_.ExecutablePath -eq $inst -or ($prev -and $_.ExecutablePath -eq $prev) -or
                                    $_.ExecutablePath -match '\\is-[^\\]+\.tmp\\|\\vc_redist')
        } | ForEach-Object { $procs[[int]$_.ProcessId] = $_.ExecutablePath }
        if ($procs.Count) {
            $c = @(Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $procs.ContainsKey([int]$_.OwningProcess) -and $_.State -ne 'Listen' -and
                     $_.RemoteAddress -notin @('127.0.0.1', '::1', '0.0.0.0', '::') } |
                   ForEach-Object { "TCP $($_.RemoteAddress):$($_.RemotePort) $($_.State) $($procs[[int]$_.OwningProcess])" })
            foreach ($l in $c) { if (-not $seen[$l]) { $seen[$l] = 1; Add-Content $log "$(Get-Date -Format o) $l" } }
        }
        Start-Sleep -Milliseconds 300
    }
}

# ------------------------------------------------------- 1. clean machine
Write-Host "== clean machine"
if ((Test-Path $RegApp) -or (Test-Path $Exe)) { Fail "the suite is already installed" } else { Pass "the suite is not installed" }
if (Test-Path $UserData) { Write-Host "note: $UserData exists before installing" } else { Pass "no user data before installing" }
New-Item -ItemType Directory -Force -Path $Docs | Out-Null
Copy-Item (Join-Path $Samples 'Sample.*') $Docs -Exclude '*.md'
# the first-start question about default applications is answered once, as a user does
New-Item -Force -Path $UserReg | Out-Null
Set-ItemProperty $UserReg -Name ignoreAssocMsg -Value 'true'

# -------------------------------------------------------------- 2. install
$first = if ($Previous) { $Previous } else { $Installer }
$code = Run-Setup $first 'install.log'
if ($code -eq 0) { Pass "installed $([IO.Path]::GetFileName($first)) silently, offline" } else { Fail "installer exit code $code" }
if (-not (Test-Path $Exe)) { Fail "no $Exe"; Write-Host "failures: $script:Fails"; exit 1 }
Close-Apps
Check-Installed 'after install'

# ---------------------------------------------------------------- 3. use
Write-Host "== use"
foreach ($app in $Apps.Keys) { Open-Document $app $(if ($Previous) { 'previous build' } else { 'first use' }) }
Save-Screen '3-documents'
Wait-Recents
Close-Apps
Check-Recents 'before the upgrade'
New-Item -ItemType Directory -Force -Path (Join-Path $UserData 'DesktopEditors') | Out-Null
Set-Content (Join-Path $UserData 'DesktopEditors\sos-release-marker.txt') "user data $(Get-Date)"
Set-ItemProperty $UserReg -Name SosReleaseMarker -Value 'keep me'
Set-ItemProperty $UserReg -Name locale -Value 'fr-FR'
$regBefore = (Get-ItemProperty $UserReg | Out-String)
$snap = Snapshot
$snap | Set-Content (Join-Path $Out 'user-files-before.txt')
Write-Host "user files: $(@($snap).Count)"

# ------------------------------------------------------------- 4. upgrade
if ($Previous) {
    Write-Host "== upgrade"
    $code = Run-Setup $Installer 'upgrade.log'
    if ($code -eq 0) { Pass "upgraded to $([IO.Path]::GetFileName($Installer)) silently, offline" } else { Fail "upgrade exit code $code" }
    Close-Apps
    $diff = Compare-Object @($snap) @(Snapshot)
    if (-not $diff) { Pass "the upgrade kept every user file unchanged" } else { Fail "user files changed in the upgrade:"; $diff | Format-Table -AutoSize | Out-String | Write-Host }
    if ((Get-ItemProperty $UserReg | Out-String) -eq $regBefore) { Pass "the upgrade kept the user's settings (language included)" } else { Fail "the user's registry settings changed in the upgrade" }
    Check-Installed 'after upgrade'
    foreach ($app in $Apps.Keys) { Start-FromStartMenu $app 'after upgrade' }
    Save-Screen '4-after-upgrade'
    Start-Sleep 3
    Close-Apps
    Check-Recents 'after the upgrade and a restart'
}

# ------------------------------------------------ 5. uninstall, reinstall
Write-Host "== uninstall"
$snap = Snapshot | Where-Object { $_ -notmatch 'recents' }
Uninstall 'uninstall.log'
if (Test-Path $Exe) { Fail "program files still there" } else { Pass "uninstalled" }
if (Get-ChildItem $StartMenu, $Desktop -Filter '*.lnk' | Where-Object { $_.BaseName -match 'EuroOffice|Secure Office' }) { Fail "shortcuts left" } else { Pass "shortcuts removed" }
$diff = Compare-Object @($snap) @(Snapshot | Where-Object { $_ -notmatch 'recents' })
if (-not $diff) { Pass "the uninstall kept settings, profiles and documents" } else { Fail "user files changed in the uninstall:"; $diff | Format-Table -AutoSize | Out-String | Write-Host }
if (RecentsFile) { Pass "recent documents kept after the uninstall" } else { Fail "recent documents gone after the uninstall" }

Write-Host "== reinstall"
$code = Run-Setup $Installer 'reinstall.log'
if ($code -eq 0) { Pass "installed again silently, offline" } else { Fail "reinstall exit code $code" }
Close-Apps
Check-Installed 'after reinstall'
if ((Get-ItemProperty $UserReg -ErrorAction SilentlyContinue).SosReleaseMarker -eq 'keep me' -and (Get-ItemProperty $UserReg).locale -eq 'fr-FR') {
    Pass "the user's settings survived uninstall and reinstall"
} else { Fail "the user's settings were lost by uninstall and reinstall" }
foreach ($app in $Apps.Keys) { Start-FromStartMenu $app 'after reinstall' }
Save-Screen '5-after-reinstall'
Start-Sleep 3
Close-Apps
Check-Recents 'after reinstalling'
Start-Process -FilePath (Join-Path $Docs 'Sample.odt')
if (Wait-Window '^\*?Sample\.odt( .*)? - EuroOffice Writer$' 150) { Pass "double-click on Sample.odt opens Writer after reinstall" } else { Fail "Sample.odt did not open in Writer after reinstall"; Show-Windows }
Close-Apps

# ------------------------------------------------- 6. CSV double-click
Write-Host "== CSV double-click"
$csvFails = 0
for ($i = 1; $i -le 6; $i++) {
    $fresh = $i -le 3
    Close-Apps
    if ($fresh) {
        # a user who has never started the suite
        Remove-Item $UserData -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item $UserReg -Recurse -Force -ErrorAction SilentlyContinue
    }
    $f = Join-Path $Docs "Csv-run-$i.csv"
    Copy-Item (Join-Path $Docs 'Sample.csv') $f -Force
    Start-Process -FilePath $f
    $re = '^\*?' + [regex]::Escape([IO.Path]::GetFileName($f)) + '( .*)? - EuroOffice Sheet$'
    $w = Wait-Window $re 150
    $label = "run $i ($(if ($fresh) { 'new user profile' } else { 'existing profile' }))"
    if (-not $w) { Fail "CSV $label did not open in Sheet"; $csvFails++; Show-Windows; Show-Crashes; Save-Screen "6-csv-$i"; continue }
    Start-Sleep 15
    if (Get-Process -Id $w.pid -ErrorAction SilentlyContinue) {
        $still = Wait-Window $re 2
        if ($still) { Pass "CSV $label opened in Sheet and Sheet is still up 15 s later" } else { Fail "CSV $label window closed within 15 s"; $csvFails++; Show-Windows }
    } else { Fail "CSV $label opened, then Sheet (pid $($w.pid)) quit within 15 s"; $csvFails++; Show-Windows; Show-Crashes }
    Save-Screen "6-csv-$i"
}
Write-Host "CSV double-click: $(6 - $csvFails) of 6 kept Sheet open"
Close-Apps

# ------------------------------------------------- 7. offline result
Stop-Job $watcher -ErrorAction SilentlyContinue; Remove-Job $watcher -Force -ErrorAction SilentlyContinue
Get-NetFirewallRule -DisplayName 'SOS release offline *' | Remove-NetFirewallRule
if ((Test-Path $watchLog) -and (Get-Content $watchLog)) {
    Fail "the installer or the applications tried to reach the network:"
    Get-Content $watchLog | Select-Object -First 30 | ForEach-Object { Write-Host "    $_" }
} else { Pass "no network connection attempts by the installer or the applications" }

Write-Host "failures: $script:Fails"
exit ([int]($script:Fails -gt 0))
