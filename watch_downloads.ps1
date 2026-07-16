# Litmanger PDF Auto-Archiver
# Watches the Downloads folder for new PDFs and copies them to pdfs/
# Usage: powershell -ExecutionPolicy Bypass -File watch_downloads.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PdfDir = Join-Path $ScriptDir "pdfs"
$Downloads = [Environment]::GetFolderPath("UserProfile") + "\Downloads"

if (-not (Test-Path $PdfDir)) {
    New-Item -ItemType Directory -Path $PdfDir | Out-Null
}

Write-Host "Litmanger PDF Auto-Archiver" -ForegroundColor Cyan
Write-Host "  Watching : $Downloads" -ForegroundColor Yellow
Write-Host "  Target   : $PdfDir" -ForegroundColor Yellow
Write-Host "  Ctrl+C to stop`n" -ForegroundColor Gray

$Watcher = New-Object System.IO.FileSystemWatcher
$Watcher.Path = $Downloads
$Watcher.Filter = "*.pdf"
$Watcher.IncludeSubdirectories = $false
$Watcher.EnableRaisingEvents = $true

$Action = {
    $path = $Event.SourceEventArgs.FullPath
    $name = $Event.SourceEventArgs.Name
    $changeType = $Event.SourceEventArgs.ChangeType

    # Wait for file to finish writing (skip temp files)
    if ($name -like "*.crdownload" -or $name -like "*.tmp") { return }
    Start-Sleep -Seconds 1

    if (Test-Path $path) {
        try {
            $dest = Join-Path $PdfDir $name
            Copy-Item -Path $path -Destination $dest -Force
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] ARCHIVED: $name" -ForegroundColor Green
        } catch {
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] ERROR: $name — $_" -ForegroundColor Red
        }
    }
}

Register-ObjectEvent $Watcher "Created" -Action $Action | Out-Null
Register-ObjectEvent $Watcher "Changed" -Action $Action | Out-Null

try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    $Watcher.EnableRaisingEvents = $false
    $Watcher.Dispose()
}
