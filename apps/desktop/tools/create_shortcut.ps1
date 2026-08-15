$root = (Resolve-Path "$PSScriptRoot\..\..\..").Path
$python = Join-Path $root '.venv\Scripts\pythonw.exe'
$entrypoint = Join-Path $root 'apps\desktop\launch.py'
$icon = Join-Path $root 'apps\desktop\assets\skinflow.ico'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Skinflow.lnk'

if (-not (Test-Path $python)) {
  throw "pythonw.exe not found at $python"
}
if (-not (Test-Path $entrypoint)) {
  throw "Desktop entrypoint not found at $entrypoint"
}
if (-not (Test-Path $icon)) {
  throw "Skinflow icon not found at $icon"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $python
$shortcut.Arguments = "`"$entrypoint`""
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = "$icon,0"
$shortcut.Description = 'Skinflow CS2 交易工作台'
$shortcut.Save()
Write-Output "Created $shortcutPath"
