<#
.SYNOPSIS
  Common dev tasks for the Archive Reconstruction Platform (PowerShell equivalent of the Makefile).

.EXAMPLE
  .\tasks.ps1 test
  .\tasks.ps1 web
  .\tasks.ps1 demo
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "test", "install", "demo", "web", "dedup", "clean")]
    [string]$Task = "help"
)

$env:PYTHONPATH = "src"

switch ($Task) {
    "test"    { python tests/run_all.py }
    "install" { python -m pip install -e . }
    "demo"    {
        python -m arc.cli timeline examples/events.json -o timeline.html
        Write-Host "Open timeline.html in a browser."
    }
    "web"     { python -m arc.cli web }
    "dedup"   { python -m arc.cli dedup examples/threads }
    "clean"   {
        Remove-Item -ErrorAction SilentlyContinue timeline.html, arc.db
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue `
            src/arc/__pycache__, tests/__pycache__
    }
    default   {
        Write-Host "Tasks: test | install | demo | web | dedup | clean"
        Write-Host "Usage: .\tasks.ps1 <task>"
    }
}
