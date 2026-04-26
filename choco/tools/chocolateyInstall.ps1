$ErrorActionPreference = 'Stop'

$version    = '0.1.1'
$url        = "https://github.com/guilhermegor/blueprintx/archive/refs/tags/v${version}.tar.gz"
$sha256     = 'c697f4e68d687163f8752c196402f678a9ca5ef045503ad2784a4cd939b1fd24'
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
