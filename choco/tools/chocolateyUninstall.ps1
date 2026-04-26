$ErrorActionPreference = 'Stop'

$installDir = Join-Path $env:LOCALAPPDATA 'blueprintx'
Remove-Item -Recurse -Force $installDir -ErrorAction SilentlyContinue
