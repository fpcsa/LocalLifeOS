[CmdletBinding()]
param(
    [switch]$RemoveVolumes
)

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    if ($RemoveVolumes) {
        docker compose down --volumes
    }
    else {
        docker compose down
    }
}
finally {
    Pop-Location
}
