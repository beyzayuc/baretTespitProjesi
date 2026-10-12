param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'

function Find-PythonRuntime {
    # Windows PowerShell 5.1 converts native stderr to terminating errors
    # under Stop, even when it is redirected. Failed probes are expected.
    $ErrorActionPreference = 'SilentlyContinue'
    $probeCode = 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,13); print(sys.executable)'
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($version in @('-3.12', '-3.13', '-3.11', '-3.10')) {
            $candidate = & py $version -c $probeCode 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate) { return [string]($candidate | Select-Object -Last 1) }
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidate = & python -c $probeCode 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) { return [string]($candidate | Select-Object -Last 1) }
    }
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    return $null
}

function Test-PythonPackages([string]$Executable) {
    $ErrorActionPreference = 'SilentlyContinue'
    & $Executable -c 'import ultralytics, cv2, PIL, tkinter, pyodbc, lap, scipy' 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}
Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    $basePython = Find-PythonRuntime
    if (-not $basePython) { throw 'Python bulunamadi. Python 3.12 kurup BASLAT.cmd dosyasini yeniden acin.' }
    if ($CheckOnly) { Write-Output $basePython; return }
    & $basePython -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python ortami olusturulamadi.' }
}
if ($CheckOnly) { Write-Output $venvPython; return }
if (-not (Test-PythonPackages $venvPython)) {
    Write-Host 'Ilk kurulum: gerekli paketler indiriliyor...'
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Paket kurulumu basarisiz. Internet baglantisini kontrol edip tekrar deneyin.' }
}
& $venvPython main.py
if ($LASTEXITCODE -ne 0) { throw 'Uygulama baslatilamadi. Yukaridaki hata ayrintilarini kontrol edin.' }
