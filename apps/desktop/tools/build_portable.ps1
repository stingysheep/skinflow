[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$OutputDirectory,
    [string]$Version = "0.1.1"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$apiPath = Join-Path $root "apps\api"
$desktopPath = Join-Path $root "apps\desktop"
$webDist = Join-Path $root "apps\web\dist"
$desktopAssets = Join-Path $desktopPath "assets"
$entryPoint = Join-Path $desktopPath "launch.py"
$distPath = Join-Path $OutputDirectory "dist"
$workPath = Join-Path $OutputDirectory "build"
$specPath = Join-Path $OutputDirectory "spec"
$portablePath = Join-Path $distPath "Skinflow"
$archivePath = Join-Path $OutputDirectory "Skinflow-$Version-windows-x64.zip"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found: $python"
}
if ((Test-Path -LiteralPath $portablePath) -or (Test-Path -LiteralPath $archivePath)) {
    throw "Refusing to overwrite an existing portable build output. Choose a new OutputDirectory."
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Push-Location $root
try {
    npm run build
    & $python -m PyInstaller `
        --onedir `
        --name Skinflow `
        --paths $apiPath `
        --paths $desktopPath `
        --hidden-import skinflow_desktop.launcher `
        --collect-all webview `
        --add-data "$webDist;apps/web/dist" `
        --add-data "$desktopAssets;apps/desktop/assets" `
        --distpath $distPath `
        --workpath $workPath `
        --specpath $specPath `
        $entryPoint
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    Compress-Archive -Path (Join-Path $portablePath "*") -DestinationPath $archivePath
}
finally {
    Pop-Location
}
