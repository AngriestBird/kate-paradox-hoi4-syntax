# Install the HOI4 Kate syntax-highlighting files for the current user.
# Works from a cloned repo or an extracted release archive.
param(
    [ValidateNotNullOrEmpty()]
    [string]$Dest = (Join-Path $env:LOCALAPPDATA 'org.kde.syntax-highlighting\syntax')
)

$ErrorActionPreference = 'Stop'
$src  = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

foreach ($f in 'hoi4.xml', 'hoi4-localisation.xml', 'hoi4-lua.xml') {
    Copy-Item -LiteralPath (Join-Path $src $f) -Destination (Join-Path $Dest $f) -Force
    Write-Host "installed $f -> $Dest"
}

Write-Host 'Done. Restart Kate to load the new highlighting.'
