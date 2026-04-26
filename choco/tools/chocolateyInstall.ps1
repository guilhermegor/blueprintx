$ErrorActionPreference = 'Stop'

$version    = '0.1.7'
$url        = "https://github.com/guilhermegor/blueprintx/archive/refs/tags/v${version}.tar.gz"
$sha256     = '2aa795e6cb04ee191a0025b5e1f356152b920c85f49405c134f35729a7fbdcbe'
$installDir = Join-Path $env:LOCALAPPDATA 'blueprintx'
$toolsDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition

$archive = Join-Path $toolsDir "blueprintx-${version}.tar.gz"
Get-ChocolateyWebFile -PackageName 'blueprintx' -FileFullPath $archive `
    -Url $url -Checksum $sha256 -ChecksumType 'sha256'

Remove-Item -Recurse -Force $installDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
tar -xzf $archive -C $installDir --strip-components=1

Get-ChildItem -Recurse -Filter '*.sh' $installDir | ForEach-Object { $_.IsReadOnly = $false }

$shim = @"
@echo off
bash "%LOCALAPPDATA%\blueprintx\bin\blueprintx.sh" %*
"@
$shim | Set-Content (Join-Path $toolsDir 'blueprintx.cmd') -Encoding ASCII
