# Install the HOI4 Kate syntax-highlighting files for the current user.
# Works from a cloned repo or an extracted release archive.
$ErrorActionPreference = 'Stop'

$dest = Join-Path $env:USERPROFILE 'AppData\Local\org.kde.syntax-highlighting\syntax'
$src  = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $dest | Out-Null

foreach ($f in 'hoi4.xml', 'hoi4-localisation.xml', 'hoi4-lua.xml') {
    Copy-Item (Join-Path $src $f) (Join-Path $dest $f) -Force
    Write-Host "installed $f -> $dest"
}

Write-Host 'Done. Restart Kate to load the new highlighting.'
