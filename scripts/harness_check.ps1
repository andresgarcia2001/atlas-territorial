param(
    [switch] $BackendOnly,
    [switch] $FrontendOnly,
    [switch] $BuildFrontend,
    [switch] $PostGIS
)

$ErrorActionPreference = "Stop"

function Test-Command {
    param([string] $Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonCommand {
    $venvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return @($venvPython)
    }
    if (Test-Command "py") {
        return @("py", "-3.12")
    }
    if (Test-Command "python") {
        return @("python")
    }
    throw "No Python executable found. Create .venv or install Python 3.12."
}

function Invoke-Step {
    param(
        [string] $Name,
        [scriptblock] $Action
    )
    Write-Host ""
    Write-Host "== $Name =="
    & $Action
    Write-Host "OK: $Name"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$runBackend = -not $FrontendOnly
$runFrontend = -not $BackendOnly

Push-Location $repoRoot
try {
    if ($runBackend) {
        Invoke-Step "backend pytest" {
            $python = @(Get-PythonCommand)
            $pythonExe = $python[0]
            $pythonArgs = @()
            if ($python.Count -gt 1) {
                $pythonArgs = $python[1..($python.Count - 1)]
            }
            $pytestArgs = @("-m", "not postgis")
            if ($PostGIS) {
                $pytestArgs = @()
            }
            & $pythonExe @pythonArgs -m pytest @pytestArgs
        }
    }

    if ($runFrontend) {
        Invoke-Step "frontend unit tests" {
            if (-not (Test-Command "npm")) {
                throw "npm is not available on PATH."
            }
            Push-Location "frontend"
            try {
                npm run test:unit
                if ($BuildFrontend) {
                    npm run build
                }
            }
            finally {
                Pop-Location
            }
        }
    }
}
finally {
    Pop-Location
}
