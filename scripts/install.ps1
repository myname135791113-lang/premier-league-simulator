# Sets up Matchday on this PC:
#   - a desktop shortcut that opens the app
#   - a scheduled full update every Monday at 06:00 and a quick update every Friday at 18:00
#     (both run when the PC is next on if it was off at that time)
# Run again at any time; it replaces what it created before.
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "Python environment not found at $pythonw. Create it first (see README)." }

# Desktop shortcut
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut((Join-Path $desktop "Matchday.lnk"))
$lnk.TargetPath = $pythonw
$lnk.Arguments = "-m sim.app.server --open"
$lnk.WorkingDirectory = $root
$lnk.Description = "Matchday: Premier League predictions"
$icon = Join-Path $root "src\sim\app\static\matchday.ico"
if (Test-Path $icon) { $lnk.IconLocation = $icon }
$lnk.Save()
Write-Output "Shortcut created: $desktop\Matchday.lnk"

# Scheduled updates
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$tasks = @(
  @{ Name = "Football Simulator Weekly"; Kind = "full";  Trigger = (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 06:00); Desc = "Matchday full update: results, xG, Opta stats, team news, season outlook, predictions" },
  @{ Name = "Football Simulator Friday"; Kind = "light"; Trigger = (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 18:00); Desc = "Matchday quick update: team news and bookmaker odds before the weekend" }
)
foreach ($t in $tasks) {
  $action = New-ScheduledTaskAction -Execute $pythonw -Argument "-m sim.weekly --kind $($t.Kind)" -WorkingDirectory $root
  Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $t.Trigger -Settings $settings -Description $t.Desc -Force | Out-Null
  $next = (Get-ScheduledTaskInfo -TaskName $t.Name).NextRunTime
  Write-Output "Scheduled: $($t.Name), next run $next"
}
