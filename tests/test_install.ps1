$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $repo 'install.ps1'
$root = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $root | Out-Null

function Assert-Installed([string]$Path) {
    foreach ($file in 'hoi4.xml', 'hoi4-localisation.xml', 'hoi4-lua.xml') {
        $expected = (Get-FileHash -LiteralPath (Join-Path $repo $file)).Hash
        $actual = (Get-FileHash -LiteralPath (Join-Path $Path $file)).Hash
        if ($actual -ne $expected) {
            throw "Installed file differs: $file"
        }
    }
}

$originalLocalAppData = $env:LOCALAPPDATA
Push-Location $root
try {
    $env:LOCALAPPDATA = Join-Path $root 'redirected AppData'
    & $installer
    $default = Join-Path $env:LOCALAPPDATA 'org.kde.syntax-highlighting\syntax'
    Assert-Installed $default

    $env:LOCALAPPDATA = Join-Path $root 'unused AppData'
    $custom = Join-Path $root 'custom [syntax]'
    & $installer -Dest $custom
    Assert-Installed $custom
    if (Test-Path -LiteralPath $env:LOCALAPPDATA) {
        throw 'A custom destination also wrote to the default path'
    }

    Set-Content -LiteralPath (Join-Path $custom 'hoi4.xml') -Value 'old version'
    & $installer -Dest $custom
    Assert-Installed $custom

    $rejected = $false
    try {
        & $installer -Dest ''
    } catch [System.Management.Automation.ParameterBindingException] {
        if ($_.FullyQualifiedErrorId -ne 'ParameterArgumentValidationError,install.ps1') {
            throw
        }
        $rejected = $true
    }
    if (-not $rejected) {
        throw 'An empty destination was accepted'
    }
    if (Test-Path -LiteralPath $env:LOCALAPPDATA) {
        throw 'An invalid destination wrote to the default path'
    }
} finally {
    $env:LOCALAPPDATA = $originalLocalAppData
    Pop-Location
}

Write-Output 'Passed: redirected AppData, custom destination, reinstall, empty destination'
