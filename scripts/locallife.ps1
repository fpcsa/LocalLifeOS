[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArguments
)

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $repositoryRoot "apps/api"
$venvPython = Join-Path $apiRoot ".venv/Scripts/python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

Push-Location $apiRoot
try {
    & $python -m app.launcher @CommandArguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
