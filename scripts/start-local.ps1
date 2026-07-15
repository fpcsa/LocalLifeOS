[CmdletBinding()]
param(
    [switch]$Detached
)

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    if ($Detached) {
        docker compose up --build --detach
    }
    else {
        docker compose up --build
    }
}
finally {
    Pop-Location
}
