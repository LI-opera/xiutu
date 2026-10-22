param([switch]$OfflineOnly)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ((Get-Location).Path -ne $projectRoot) { throw "Run from the xiutu-v5 project root" }
$targets = @("tests/unit", "tests/integration", "tests/contract", "tests/probes")
if ($OfflineOnly) {
    $targets = @("tests/unit", "tests/contract")
} elseif (-not $env:TEST_DATABASE_URL) {
    throw "TEST_DATABASE_URL is mandatory; no development or old DB fallback"
}
# Settings loads the project .env when DATABASE_URL is absent. Keep every
# subprocess on the explicitly supplied isolated test database.
if (-not $OfflineOnly) { $env:DATABASE_URL = $env:TEST_DATABASE_URL }
# Reject reparse points along the project path as well as the temporary parent.
# Never follow junctions/symlinks, even if they currently resolve inside the project.
function Assert-PlainDirectory([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refuse reparse path for test output: $Path"
    }
    if (-not $item.PSIsContainer) { throw "Test output path must be a directory: $Path" }
}
$ancestor = [IO.Path]::GetFullPath($projectRoot)
while ($ancestor) {
    Assert-PlainDirectory $ancestor
    $ancestor = [IO.Path]::GetDirectoryName($ancestor)
}
$tempParent = Join-Path $projectRoot ".test-runs"
$existing = Get-Item -LiteralPath $tempParent -Force -ErrorAction SilentlyContinue
if ($null -eq $existing) { [void][IO.Directory]::CreateDirectory($tempParent) }
Assert-PlainDirectory $tempParent
$runPath = Join-Path $tempParent ("run-" + [guid]::NewGuid().ToString("N"))
if (Test-Path -LiteralPath $runPath) { throw "Refuse existing test run target: $runPath" }
[void][IO.Directory]::CreateDirectory($runPath)
Assert-PlainDirectory $runPath
Write-Output "Test temporary directory: $runPath"
$pytestTemp = Join-Path $runPath "temp"
if (Test-Path -LiteralPath $pytestTemp) { throw "Refuse existing pytest target: $pytestTemp" }
# Database fixtures additionally enforce loopback:5433 and database xiutu_test_*.
uv run --frozen python -B -m pytest -p no:cacheprovider @targets -q -s --basetemp $pytestTemp
exit $LASTEXITCODE
