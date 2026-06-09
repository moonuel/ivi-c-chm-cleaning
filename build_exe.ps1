param(
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".venv")) {
    throw "Create and populate .venv first, then rerun this script."
}

$pyinstaller = Join-Path ".venv" "Scripts\pyinstaller.exe"
if (-not (Test-Path -LiteralPath $pyinstaller)) {
    throw "pyinstaller.exe not found in .venv\Scripts. Install the build extra first."
}

& $pyinstaller --onefile --name "ivi-chm" --distpath $OutputDir --workpath "build" --specpath "build" "src\ivi_chm\cli.py"
