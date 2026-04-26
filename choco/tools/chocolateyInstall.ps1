$ErrorActionPreference = 'Stop'

$version    = '0.1.6'
$url        = "https://github.com/guilhermegor/blueprintx/archive/refs/tags/v${version}.tar.gz"
$sha256     = '572b668d5a8b9fc5444b1c6c23c5226c4a42f97272a9ad941c5c1810e83f8172'
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
