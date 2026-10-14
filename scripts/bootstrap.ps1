param([string]$EnvironmentPath = ".venv")
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ((Get-Location).Path -ne $projectRoot) { throw "Run from the xiutu-v5 project root" }
$target = [IO.Path]::GetFullPath((Join-Path $projectRoot $EnvironmentPath))
if (-not $target.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar)) { throw "Environment must remain inside this project" }
if ((Test-Path -LiteralPath $target) -and -not (Test-Path -LiteralPath (Join-Path $target "pyvenv.cfg"))) {
    throw "Refuse an existing directory that is not a virtual environment"
}
node frontend/scripts/check-node.mjs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$previous = $env:UV_PROJECT_ENVIRONMENT
try {
    $env:UV_PROJECT_ENVIRONMENT = $target
    uv sync --frozen --group dev
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { $env:UV_PROJECT_ENVIRONMENT = $previous }
