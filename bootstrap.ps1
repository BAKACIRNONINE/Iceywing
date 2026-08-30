$ErrorActionPreference = "Stop"
$ExpectedVersion = "0.4.0a24"

Write-Host "* Iceywing Setup"
Write-Host ""

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logRoot = Join-Path $env:LOCALAPPDATA "Iceywing\logs"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$log = Join-Path $logRoot "$stamp-install.log"

function Set-SetupProgress(
    [int]$Percent,
    [string]$Status,
    [switch]$Completed
) {
    if ($Completed) {
        Write-Progress -Id 1 -Activity "Iceywing Setup" -Completed
        return
    }
    Write-Progress -Id 1 -Activity "Iceywing Setup" -Status $Status -PercentComplete $Percent
}

function Quote-ProcessArgument([string]$Argument) {
    if ($Argument -notmatch '[\s"]') { return $Argument }
    return '"' + $Argument.Replace('"', '\"') + '"'
}

function Invoke-LoggedProcessWithProgress(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$Status,
    [int]$Percent
) {
    $stdoutLog = "$log.stdout"
    $stderrLog = "$log.stderr"
    Remove-Item -LiteralPath $stdoutLog, $stderrLog -Force -ErrorAction SilentlyContinue

    $argumentList = @($Arguments | ForEach-Object { Quote-ProcessArgument $_ })
    $started = Get-Date
    $startOptions = @{
        FilePath = $FilePath
        ArgumentList = $argumentList
        NoNewWindow = $true
        PassThru = $true
        RedirectStandardOutput = $stdoutLog
        RedirectStandardError = $stderrLog
    }
    $process = Start-Process @startOptions

    while (-not $process.HasExited) {
        $elapsed = [int]((Get-Date) - $started).TotalSeconds
        Set-SetupProgress -Percent $Percent -Status "$Status (${elapsed}s)"
        Start-Sleep -Milliseconds 200
        $process.Refresh()
    }
    $process.WaitForExit()
    $process.Refresh()
    $exitCode = [int]$process.ExitCode

    foreach ($path in @($stdoutLog, $stderrLog)) {
        if (Test-Path -LiteralPath $path) {
            Get-Content -LiteralPath $path -ErrorAction SilentlyContinue |
                Add-Content -LiteralPath $log
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    }
    # Return an object so PowerShell cannot turn a missing scalar pipeline value
    # into an empty exit-code string at the call site.
    return [PSCustomObject]@{ ExitCode = $exitCode }
}

function Show-Failure([string]$step, [string]$hint = "") {
    Set-SetupProgress -Completed
    Write-Host ""
    Write-Host "[FAIL] $step"
    if ($hint) {
        Write-Host ""
        Write-Host $hint
    }
    if (Test-Path $log) {
        Write-Host ""
        Write-Host "Last output:"
        Get-Content $log -Tail 24
        Write-Host ""
        Write-Host "Full log: $log"
    }
}

function Get-Python {
    foreach ($candidate in @('python', 'py')) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $prefix = if ($candidate -eq 'py') { @('-3') } else { @() }
        $saved = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $cmd.Source @prefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return [PSCustomObject]@{ Exe = $cmd.Source; Prefix = $prefix }
            }
        } finally {
            $ErrorActionPreference = $saved
        }
    }
    return $null
}

function Remove-StalePipArtifacts([string]$sitePackages) {
    if (-not $sitePackages -or -not (Test-Path -LiteralPath $sitePackages)) { return }
    Get-ChildItem -LiteralPath $sitePackages -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like '~ceywing*' } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
}

function Get-InstalledIceywing(
    [string]$PythonExe,
    [string[]]$PythonArgs,
    [string]$Expected
) {
    $saved = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $installed = (& $PythonExe @PythonArgs -m iceywing --version 2>$null).Trim()
        if ($LASTEXITCODE -ne 0 -or $installed -ne $Expected) { return $null }

        $defaultScripts = (& $PythonExe @PythonArgs -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>$null).Trim()
        $userScripts = (& $PythonExe @PythonArgs -c "import sysconfig; scheme=sysconfig.get_preferred_scheme('user'); print(sysconfig.get_path('scripts', scheme=scheme))" 2>$null).Trim()
        $candidates = @(
            [PSCustomObject]@{ Scope = 'default'; Scripts = $defaultScripts },
            [PSCustomObject]@{ Scope = 'user'; Scripts = $userScripts }
        )
        foreach ($candidate in $candidates) {
            if (-not $candidate.Scripts) { continue }
            $candidateLauncher = Join-Path $candidate.Scripts 'iceywing.exe'
            if (-not (Test-Path -LiteralPath $candidateLauncher)) { continue }
            $launcherVersion = (& $candidateLauncher --version 2>$null).Trim()
            if ($LASTEXITCODE -eq 0 -and $launcherVersion -eq $Expected) {
                return [PSCustomObject]@{
                    Scope = $candidate.Scope
                    Launcher = $candidateLauncher
                }
            }
        }
        return $null
    } catch {
        return $null
    } finally {
        $ErrorActionPreference = $saved
    }
}

function Test-PermissionDenied {
    if (-not (Test-Path -LiteralPath $log)) { return $false }
    $text = Get-Content -LiteralPath $log -Raw -ErrorAction SilentlyContinue
    return $text -match '(?i)access is denied|permission denied|winerror\s*5|errno\s*13'
}

Set-SetupProgress -Percent 5 -Status "Checking Python"
$python = Get-Python
if (-not $python) {
    Add-Content $log "Python 3.11+ was not found on PATH."
    Show-Failure "Check Python" "Python 3.11+ is required."
    exit 1
}
$pythonArgs = @($python.Prefix)
$version = (& $python.Exe @pythonArgs -c "import sys; print(sys.version.split()[0])").Trim()
Set-SetupProgress -Completed
Write-Host "[OK] Check Python $version"

Set-SetupProgress -Percent 35 -Status "Locating installer wheel"
$wheelPattern = "iceywing-$ExpectedVersion-*.whl"
$wheel = Get-ChildItem -Path (Join-Path $PSScriptRoot "dist\$wheelPattern") -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $wheel) {
    Add-Content $log "Expected installer wheel '$wheelPattern' was not found."
    Show-Failure "Install / upgrade" "The Preview23 installer wheel is missing. Extract the ZIP into a clean folder and try again."
    exit 1
}

$sitePackages = (& $python.Exe @pythonArgs -c "import sysconfig; print(sysconfig.get_path('purelib'))").Trim()
$userSitePackages = (& $python.Exe @pythonArgs -c "import site; print(site.getusersitepackages())").Trim()
Remove-StalePipArtifacts $sitePackages
Remove-StalePipArtifacts $userSitePackages

$useUserInstall = $false
$alreadyCurrent = $false
$currentInstall = Get-InstalledIceywing -PythonExe $python.Exe -PythonArgs $pythonArgs -Expected $ExpectedVersion
if ($currentInstall) {
    $pipExitCode = 0
    $alreadyCurrent = $true
    $useUserInstall = $currentInstall.Scope -eq 'user'
    Add-Content $log "Iceywing $ExpectedVersion is already installed and both module and launcher checks passed."
} else {
  try {
    $baseInstallArgs = @($pythonArgs) + @(
        '-m', 'pip', 'install',
        '--disable-pip-version-check',
        '--upgrade'
    )
    $installArgs = @($baseInstallArgs) + @($wheel.FullName)
    $installOptions = @{
        FilePath = $python.Exe
        Arguments = $installArgs
        Status = "Installing / upgrading Iceywing"
        Percent = 55
    }
    $installResult = Invoke-LoggedProcessWithProgress @installOptions
    $pipExitCode = $installResult.ExitCode
  } catch {
    Add-Content $log $_.Exception.Message
    $pipExitCode = 1
  }
}

if (($null -eq $pipExitCode -or $pipExitCode -ne 0) -and
    ($installedAfterAttempt = Get-InstalledIceywing -PythonExe $python.Exe -PythonArgs $pythonArgs -Expected $ExpectedVersion)) {
    Add-Content $log "The requested Iceywing version passed module and launcher checks after the normal attempt; accepting the verified postcondition."
    $pipExitCode = 0
    $useUserInstall = $installedAfterAttempt.Scope -eq 'user'
}
if ($pipExitCode -ne 0) {
    $canUseUserSite = (& $python.Exe @pythonArgs -c "import site,sys; print(int(sys.prefix == sys.base_prefix and site.ENABLE_USER_SITE is True))").Trim() -eq '1'
    if ($canUseUserSite) {
        Set-SetupProgress -Completed
        Write-Host "[WARN] Normal install failed; retrying for the current user"
        Add-Content $log ""
        Add-Content $log "Retrying with --user"
        $userInstallArgs = @($baseInstallArgs) + @('--user', $wheel.FullName)
        $userInstallOptions = @{
            FilePath = $python.Exe
            Arguments = $userInstallArgs
            Status = "Installing Iceywing for the current user"
            Percent = 55
        }
        try {
            $installResult = Invoke-LoggedProcessWithProgress @userInstallOptions
            $pipExitCode = $installResult.ExitCode
            $useUserInstall = $pipExitCode -eq 0
        } catch {
            Add-Content $log $_.Exception.Message
            $pipExitCode = 1
        }
        if (($null -eq $pipExitCode -or $pipExitCode -ne 0) -and
            ($installedAfterUserAttempt = Get-InstalledIceywing -PythonExe $python.Exe -PythonArgs $pythonArgs -Expected $ExpectedVersion)) {
            Add-Content $log "The requested Iceywing version passed module and launcher checks after the user-scoped attempt; accepting the verified postcondition."
            $pipExitCode = 0
            $useUserInstall = $installedAfterUserAttempt.Scope -eq 'user'
        }
    }
}

if ($pipExitCode -ne 0) {
    $displayExitCode = if ($null -eq $pipExitCode) { "unknown" } else { [string]$pipExitCode }
    $failureHint = "pip exited with code $displayExitCode. No administrator window was opened."
    if (Test-PermissionDenied) {
        $failureHint += " Permission was denied; right-click Setup.bat and choose 'Run as administrator' if you trust this package."
    }
    Show-Failure "Install / upgrade" $failureHint
    exit 1
}
Remove-StalePipArtifacts $sitePackages
Remove-StalePipArtifacts $userSitePackages
Set-SetupProgress -Completed
if ($alreadyCurrent) {
    Write-Host "[OK] Install / upgrade (already current)"
} elseif ($useUserInstall) {
    Write-Host "[OK] Install / upgrade (current user)"
} else {
    Write-Host "[OK] Install / upgrade"
}

Set-SetupProgress -Percent 85 -Status "Verifying installed command"
$pathWarning = $null
try {
    $moduleVersion = (& $python.Exe @pythonArgs -m iceywing --version).Trim()
    if ($LASTEXITCODE -ne 0 -or $moduleVersion -ne $ExpectedVersion) {
        throw "python -m iceywing returned '$moduleVersion' (expected $ExpectedVersion)."
    }

    if ($useUserInstall) {
        $scriptsDir = (& $python.Exe @pythonArgs -c "import sysconfig; scheme=sysconfig.get_preferred_scheme('user'); print(sysconfig.get_path('scripts', scheme=scheme))").Trim()
    } else {
        $scriptsDir = (& $python.Exe @pythonArgs -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
    }
    $launcher = Join-Path $scriptsDir 'iceywing.exe'
    if (-not (Test-Path -LiteralPath $launcher)) { throw "pip did not create iceywing.exe at '$launcher'." }
    $cliVersion = (& $launcher --version).Trim()
    if ($LASTEXITCODE -ne 0 -or $cliVersion -ne $ExpectedVersion) {
        throw "iceywing.exe returned '$cliVersion' (expected $ExpectedVersion)."
    }

    # Remove only the obsolete Preview7/8 launcher so PATH has one canonical CLI.
    $legacyLauncher = Join-Path $env:LOCALAPPDATA 'Iceywing\bin\iceywing.cmd'
    if (Test-Path -LiteralPath $legacyLauncher) {
        Remove-Item -LiteralPath $legacyLauncher -Force -ErrorAction SilentlyContinue
    }

    $launcherPath = [IO.Path]::GetFullPath($launcher)
    $resolvedCommands = @(
        Get-Command iceywing -All -ErrorAction SilentlyContinue |
            Where-Object { $_.Path }
    )
    $otherPaths = @(
        $resolvedCommands |
            ForEach-Object { [IO.Path]::GetFullPath($_.Path) } |
            Where-Object {
                -not [string]::Equals($_, $launcherPath, [StringComparison]::OrdinalIgnoreCase)
            } |
            Select-Object -Unique
    )
    if ($otherPaths.Count -gt 0) {
        $pathWarning = "Other Iceywing commands remain on PATH: $($otherPaths -join ', ')"
    }
} catch {
    Add-Content $log $_.Exception.Message
    Show-Failure "Verify" $_.Exception.Message
    exit 1
}
Set-SetupProgress -Percent 100 -Status "Installation complete"
Set-SetupProgress -Completed
Write-Host "[OK] Verify"
if ($pathWarning) {
    Write-Host "[WARN] $pathWarning"
    Write-Host "       Installed command: $launcher"
}
Write-Host ""
Write-Host "[OK] Iceywing $ExpectedVersion ready"
