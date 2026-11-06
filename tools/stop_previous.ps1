[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$entryPath = Join-Path $projectRoot 'main.py'
$pythonPaths = @(
    (Join-Path $projectRoot '.venv\Scripts\python.exe'),
    (Join-Path $projectRoot '.venv\Scripts\pythonw.exe')
)
$builtPath = Join-Path $projectRoot 'dist\Vynn_Notify.exe'
# Match complete script arguments, never other main.py files or all Python apps.
$absoluteEntry = '(?i)(?:^|\s)(?:"' + [regex]::Escape($entryPath) + '"|' + [regex]::Escape($entryPath) + ')(?=\s|$)'
$relativeEntry = '(?i)(?:^|\s)"?(?:\.\\)?main\.py"?(?=\s|$)'
$candidates = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'Vynn_Notify.exe'"
foreach ($candidate in $candidates) {
    $isProjectPython = $pythonPaths -contains $candidate.ExecutablePath
    $isScript = $candidate.CommandLine -match $absoluteEntry -or (
        $isProjectPython -and $candidate.CommandLine -match $relativeEntry
    )
    $isBuilt = $candidate.ExecutablePath -eq $builtPath
    if (($isScript -or $isBuilt) -and $PSCmdlet.ShouldProcess("Vynn process $($candidate.ProcessId)", 'Stop')) {
        $previousProcess = Get-Process -Id $candidate.ProcessId -ErrorAction SilentlyContinue
        if ($null -ne $previousProcess) {
            Stop-Process -InputObject $previousProcess -Force
            if (-not $previousProcess.WaitForExit(5000)) {
                throw "Vynn process $($candidate.ProcessId) did not exit."
            }
        }
    }
}
