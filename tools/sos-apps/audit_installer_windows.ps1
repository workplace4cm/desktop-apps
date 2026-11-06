<#
.SYNOPSIS
    Secure Office Suite: security audit of the Windows installer.

.DESCRIPTION
    audit_installer_windows.ps1 -Installer <setup.exe> -Out <dir>

    Checks:
      1. setup.exe is built with ASLR and DEP (it runs as administrator);
      2. installing into a folder outside Program Files that an ordinary
         user prepared (with "everyone may write" permissions and a planted
         DLL in it) leaves a folder that only SYSTEM and Administrators can
         change, owned by Administrators, planted file included;
      3. the same for the installed uninstaller;
      4. every file-type open command is the quoted program path with a
         quoted "%1";
      5. no URL protocol (oo-office:), no service, no scheduled task and no
         folder in C:\ProgramData is installed;
      6. the uninstaller removes the application.
    Programs and DLLs in the application folder without ASLR or DEP are
    listed as NOTE (they come from upstream builds).
    Needs administrator rights. Run after verify_windows.ps1 (which leaves
    nothing installed).
#>
param(
    [Parameter(Mandatory)] [string]$Installer,
    [Parameter(Mandatory)] [string]$Out
)

$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Installer = (Resolve-Path $Installer).Path
$script:Fails = 0
function Pass([string]$m) { Write-Host "PASS: $m" }
function Fail([string]$m) { Write-Host "FAIL: $m"; $script:Fails++ }
function Note([string]$m) { Write-Host "NOTE: $m" }

# IMAGE_DLLCHARACTERISTICS: DYNAMIC_BASE 0x40, NX_COMPAT 0x100
function PeFlags([string]$path) {
    try {
        $fs = [IO.File]::OpenRead($path)
        try {
            $br = New-Object IO.BinaryReader($fs)
            if ($br.ReadUInt16() -ne 0x5A4D) { return $null }
            $fs.Position = 0x3C; $pe = $br.ReadInt32()
            $fs.Position = $pe
            if ($br.ReadUInt32() -ne 0x4550) { return $null }
            # optional header starts 24 bytes after "PE\0\0"; DllCharacteristics at +70
            $fs.Position = $pe + 24 + 70
            $c = $br.ReadUInt16()
            return [pscustomobject]@{ Aslr = [bool]($c -band 0x40); Dep = [bool]($c -band 0x100) }
        } finally { $fs.Dispose() }
    } catch { return $null }
}

function CheckPe([string]$path, [string]$what) {
    $f = PeFlags $path
    if (-not $f) { Fail "$what is not a readable Windows program"; return }
    if ($f.Aslr -and $f.Dep) { Pass "$what is built with ASLR and DEP" }
    else { Fail "$what is built without $(@(if (-not $f.Aslr) {'ASLR'}; if (-not $f.Dep) {'DEP'}) -join ' and ')" }
}

# 1. the installer itself
CheckPe $Installer 'setup.exe'

# 2. a folder outside Program Files, prepared by an ordinary user
$parent = 'C:\SOS Audit'
$dir = Join-Path $parent 'Secure Office Suite'
Remove-Item -Recurse -Force $parent -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $dir | Out-Null
& icacls.exe $dir /grant '*S-1-1-0:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)F' /Q | Out-Null
Set-Content -Path (Join-Path $dir 'planted.dll') -Value 'planted by an ordinary user'
& icacls.exe (Join-Path $dir 'planted.dll') /grant '*S-1-1-0:F' /Q | Out-Null

$log = Join-Path $Out 'audit-setup.log'
$p = Start-Process -FilePath $Installer -Wait -PassThru -ArgumentList @(
    '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/FULLASSOCIATION', '/NOASSOCPOLICY', "/DIR=`"$dir`"", "/LOG=`"$log`"")
if ($p.ExitCode -eq 0) { Pass "setup installed into $dir" } else { Fail "setup exit code $($p.ExitCode)" }
Get-Process DesktopEditors, editors -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# rights that let someone change a file or folder (generic ones included)
$WriteMask = 0x2 -bor 0x4 -bor 0x10 -bor 0x40 -bor 0x100 -bor 0x10000 -bor 0x40000 -bor 0x80000 -bor 0x10000000 -bor 0x40000000
$Ordinary = @{
    'S-1-1-0' = 'Everyone'; 'S-1-5-11' = 'Authenticated Users'; 'S-1-5-32-545' = 'Users'
    'S-1-5-4' = 'Interactive'; 'S-1-3-0' = 'Creator Owner'; 'S-1-5-32-546' = 'Guests'
}
function WritableBy([string]$path) {
    $acl = Get-Acl -LiteralPath $path
    $who = @()
    foreach ($a in $acl.Access) {
        if ($a.AccessControlType -ne 'Allow') { continue }
        try { $sid = $a.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { $sid = "$($a.IdentityReference)" }
        if (-not $Ordinary.ContainsKey($sid)) { continue }
        if (([int64]$a.FileSystemRights.value__ -band $WriteMask) -ne 0) { $who += "$($Ordinary[$sid]) ($($a.FileSystemRights))" }
    }
    $owner = try { (New-Object Security.Principal.NTAccount($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value } catch { $acl.Owner }
    return [pscustomobject]@{ Who = $who; Owner = $owner; Protected = $acl.AreAccessRulesProtected }
}

if (Test-Path $dir) {
    (Get-Acl -LiteralPath $dir | Format-List | Out-String) | Set-Content (Join-Path $Out 'audit-acl.txt')
    $r = WritableBy $dir
    if ($r.Owner -eq 'S-1-5-32-544') { Pass 'the application folder belongs to Administrators' } else { Fail "the application folder belongs to $($r.Owner)" }
    if (-not $r.Who) { Pass 'ordinary users cannot write in the application folder' } else { Fail "ordinary users can write in the application folder: $($r.Who -join ', ')" }
    if ($r.Protected) { Pass 'the application folder inherits nothing from the drive' } else { Fail 'the application folder still inherits permissions from the drive' }

    $files = @(Get-ChildItem -LiteralPath $dir -Recurse -File -ErrorAction SilentlyContinue)
    $open = @()
    foreach ($f in $files) { $w = WritableBy $f.FullName; if ($w.Who -or (($w.Owner -ne 'S-1-5-32-544') -and ($w.Owner -ne 'S-1-5-18'))) { $open += $f.FullName } }
    if (-not $open) { Pass "none of the $($files.Count) files can be changed by ordinary users (planted file included)" }
    else { Fail "$($open.Count) files can be changed by ordinary users or belong to them:"; $open | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" } }

    # 3. the uninstaller
    $unins = Get-ChildItem -LiteralPath $dir -Filter 'unins*.exe' | Select-Object -First 1
    if ($unins) { CheckPe $unins.FullName 'the uninstaller' } else { Fail 'no uninstaller in the application folder' }

    $weak = @()
    foreach ($f in $files | Where-Object { $_.Extension -in '.exe', '.dll' }) {
        $pe = PeFlags $f.FullName
        if ($pe -and -not ($pe.Aslr -and $pe.Dep)) { $weak += $f.FullName.Substring($dir.Length + 1) }
    }
    $weak | Set-Content (Join-Path $Out 'audit-no-aslr-dep.txt')
    if ($weak) { Note "$($weak.Count) bundled programs/DLLs lack ASLR or DEP (upstream builds): $(($weak | Select-Object -First 10) -join ', ')" }
    else { Pass 'every bundled program and DLL is built with ASLR and DEP' }
} else {
    Fail "$dir does not exist after setup"
}

# 4. file-type open commands
$exe = Join-Path $dir 'DesktopEditors.exe'
$cmds = @()
foreach ($k in Get-ChildItem 'HKLM:\SOFTWARE\Classes' -ErrorAction SilentlyContinue |
               Where-Object { $_.PSChildName -match '^(ASC|SecureOfficeSuite)\.' }) {
    $c = (Get-ItemProperty -LiteralPath "$($k.PSPath)\shell\open\command" -ErrorAction SilentlyContinue).'(default)'
    if ($c) { $cmds += [pscustomobject]@{ Key = $k.PSChildName; Command = $c } }
}
$bad = $cmds | Where-Object { -not $_.Command.StartsWith("`"$exe`"", [StringComparison]::OrdinalIgnoreCase) -or $_.Command -notmatch '"%1"$' }
if (-not $cmds) { Fail 'no file-type open commands found' }
elseif (-not $bad) { Pass "all $($cmds.Count) file-type open commands quote the program and the document" }
else { Fail 'unquoted or foreign open commands:'; $bad | ForEach-Object { Write-Host "  $($_.Key): $($_.Command)" } }

# 5. nothing that listens, starts by itself or lives in C:\ProgramData
if (Test-Path 'HKLM:\SOFTWARE\Classes\oo-office') { Fail 'the oo-office: URL protocol is registered' } else { Pass 'no oo-office: URL protocol' }
$proto = Get-ChildItem 'HKLM:\SOFTWARE\Classes' -ErrorAction SilentlyContinue | Where-Object {
    $_.GetValueNames() -contains 'URL Protocol' -and
    "$((Get-ItemProperty -LiteralPath "$($_.PSPath)\shell\open\command" -ErrorAction SilentlyContinue).'(default)')" -like "*$dir*" }
if ($proto) { Fail "URL protocols open the application: $(($proto | ForEach-Object PSChildName) -join ', ')" } else { Pass 'no URL protocol opens the application' }
$svc = Get-CimInstance Win32_Service | Where-Object { $_.PathName -like "*$dir*" }
if ($svc) { Fail "services installed: $(($svc | ForEach-Object Name) -join ', ')" } else { Pass 'no service installed' }
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { ($_.Actions | ForEach-Object Execute) -like "*$dir*" }
if ($tasks) { Fail "scheduled tasks installed: $(($tasks | ForEach-Object TaskName) -join ', ')" } else { Pass 'no scheduled task installed' }
$pd = Join-Path $env:ProgramData 'Secure Office Suite'
if (Test-Path $pd) { Fail "setup made $pd (every user can write in C:\ProgramData)" } else { Pass 'nothing in C:\ProgramData' }

# 6. uninstall
if ($unins) {
    $p = Start-Process -FilePath $unins.FullName -Wait -PassThru -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
    Start-Sleep -Seconds 5
    if (Test-Path $exe) { Fail 'the uninstaller left DesktopEditors.exe behind' } else { Pass 'the uninstaller removed the application' }
}
Remove-Item -Recurse -Force $parent -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Windows installer audit: $script:Fails failure(s)"
exit [int]($script:Fails -gt 0)
