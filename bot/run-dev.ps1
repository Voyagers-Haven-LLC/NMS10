# Local dev runner for Windows.
$ErrorActionPreference = "Stop"
$BotDir = Split-Path -Parent $PSCommandPath
$RepoRoot = Split-Path -Parent $BotDir

if (-not (Test-Path "$BotDir\.venv")) {
  py -3 -m venv "$BotDir\.venv"
  & "$BotDir\.venv\Scripts\python.exe" -m pip install -q --upgrade pip
  & "$BotDir\.venv\Scripts\python.exe" -m pip install -q -r "$BotDir\requirements.txt"
}

# Load .env if present
if (Test-Path "$BotDir\.env") {
  Get-Content "$BotDir\.env" | ForEach-Object {
    if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)$') {
      [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
    }
  }
}

Set-Location $RepoRoot
& "$BotDir\.venv\Scripts\python.exe" -m bot.main @args
