$ErrorActionPreference = 'Stop'

$version    = '0.1.3'
$url        = "https://github.com/guilhermegor/blueprintx/archive/refs/tags/v${version}.tar.gz"
$sha256     = '517292574a3b9eab35e55b8f1ca08c671596bbd43b1de0205216b0efeeb816e2'
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
