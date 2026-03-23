# ================================================================
#       Google Drive Sync - Health Check PowerShell Script
# ================================================================

param(
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Continue"
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition

try {
    Write-Host "🔍 Google Drive Sync Health Check - $(Get-Date)"
    Write-Host "=" * 60
    
    # Check 1: Active Python Processes
    Write-Host "`n📊 Checking active sync processes..."
    $pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*drive_sync_production.py*"
    }
    
    if ($pythonProcesses) {
        Write-Host "⚠️  Warning: $($pythonProcesses.Count) sync process(es) currently running"
        foreach ($proc in $pythonProcesses) {
            $runtime = (Get-Date) - $proc.StartTime
            Write-Host "   Process ID: $($proc.Id), Runtime: $($runtime.TotalMinutes.ToString('F1')) minutes"
        }
    } else {
        Write-Host "✅ No sync processes currently running"
    }
    
    # Check 2: Recent Sync Activity
    Write-Host "`n📋 Checking recent sync activity..."
    $logFiles = Get-ChildItem "$ScriptPath\logs\drive_sync_*.log" -ErrorAction SilentlyContinue | 
                Sort-Object LastWriteTime -Descending | 
                Select-Object -First 5
    
    if ($logFiles) {
        $lastLogFile = $logFiles[0]
        $lastLogAge = (Get-Date) - $lastLogFile.LastWriteTime
        
        Write-Host "📄 Last log file: $($lastLogFile.Name) ($(($lastLogAge.TotalHours).ToString('F1')) hours ago)"
        
        # Check for recent success
        $successPattern = "✅ Sync operation completed successfully"
        $lastSuccess = Select-String -Path $lastLogFile.FullName -Pattern $successPattern | Select-Object -Last 1
        
        if ($lastSuccess) {
            Write-Host "✅ Last successful sync found in recent logs"
        } else {
            Write-Host "⚠️  Warning: No recent successful sync completion found"
        }
        
        # Check for errors
        $errorPattern = "ERROR|FAILED|💥"
        $recentErrors = Select-String -Path $lastLogFile.FullName -Pattern $errorPattern | Select-Object -Last 3
        
        if ($recentErrors) {
            Write-Host "❌ Recent errors found:"
            foreach ($error in $recentErrors) {
                Write-Host "   Line $($error.LineNumber): $($error.Line.Substring(0, [Math]::Min(100, $error.Line.Length)))..."
            }
        } else {
            Write-Host "✅ No recent errors in latest log"
        }
    } else {
        Write-Host "⚠️  Warning: No log files found"
    }
    
    # Check 3: Disk Space
    Write-Host "`n💾 Checking disk space..."
    $dataPath = Join-Path $ScriptPath "data"
    $drive = (Get-Item $dataPath -ErrorAction SilentlyContinue).Root.Name -replace '\\', ''
    
    if (-not $drive) {
        $drive = "C:"
    }
    
    $diskInfo = Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DeviceID -eq $drive}
    
    if ($diskInfo) {
        $freeSpaceGB = [math]::Round($diskInfo.FreeSpace / 1GB, 2)
        $totalSpaceGB = [math]::Round($diskInfo.Size / 1GB, 2)
        $usedPercent = [math]::Round(($diskInfo.Size - $diskInfo.FreeSpace) / $diskInfo.Size * 100, 1)
        
        Write-Host "📊 Drive $drive : $freeSpaceGB GB free / $totalSpaceGB GB total ($usedPercent% used)"
        
        if ($freeSpaceGB -lt 10) {
            Write-Host "❌ Critical: Very low disk space ($freeSpaceGB GB remaining)"
            $exitCode = 1
        } elseif ($freeSpaceGB -lt 50) {
            Write-Host "⚠️  Warning: Low disk space ($freeSpaceGB GB remaining)"
        } else {
            Write-Host "✅ Disk space sufficient"
        }
    }
    
    # Check 4: Data Directory Size
    Write-Host "`n📁 Checking sync data directory..."
    if (Test-Path $dataPath) {
        $dataSize = (Get-ChildItem $dataPath -Recurse -ErrorAction SilentlyContinue | 
                    Measure-Object -Property Length -Sum).Sum
        
        if ($dataSize) {
            $dataSizeGB = [math]::Round($dataSize / 1GB, 2)
            Write-Host "📦 Data directory size: $dataSizeGB GB"
        } else {
            Write-Host "📦 Data directory is empty or inaccessible"
        }
        
        # Count files
        $fileCount = (Get-ChildItem $dataPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        Write-Host "📄 Total files in sync directory: $fileCount"
    } else {
        Write-Host "⚠️  Warning: Data directory not found: $dataPath"
    }
    
    # Check 5: Configuration Files
    Write-Host "`n⚙️  Checking configuration files..."
    $configFile = Join-Path $ScriptPath "config.json"
    $credentialsFile = Join-Path $ScriptPath "credentials.json"
    
    if (Test-Path $configFile) {
        Write-Host "✅ config.json found"
        try {
            $config = Get-Content $configFile -Raw | ConvertFrom-Json
            if ($config.drive_settings.folder_id) {
                Write-Host "✅ Google Drive folder ID configured"
            } else {
                Write-Host "⚠️  Warning: No Google Drive folder ID in config"
            }
        } catch {
            Write-Host "❌ Error: Invalid config.json format"
        }
    } else {
        Write-Host "❌ Error: config.json not found"
        $exitCode = 1
    }
    
    if (Test-Path $credentialsFile) {
        Write-Host "✅ credentials.json found"
    } else {
        Write-Host "❌ Error: credentials.json not found"
        $exitCode = 1
    }
    
    # Check 6: Network Connectivity
    Write-Host "`n🌐 Checking network connectivity..."
    try {
        $googleTest = Test-NetConnection -ComputerName "googleapis.com" -Port 443 -WarningAction SilentlyContinue
        if ($googleTest.TcpTestSucceeded) {
            Write-Host "✅ Google APIs accessible"
        } else {
            Write-Host "❌ Error: Cannot reach Google APIs"
            $exitCode = 1
        }
    } catch {
        Write-Host "⚠️  Warning: Network connectivity test failed"
    }
    
    # Check 7: Authentication Token
    Write-Host "`n🔐 Checking authentication..."
    $tokenFile = Join-Path $ScriptPath "state\token.pickle"
    if (Test-Path $tokenFile) {
        $tokenAge = (Get-Date) - (Get-Item $tokenFile).LastWriteTime
        Write-Host "✅ Authentication token found (last updated $($tokenAge.Days) days ago)"
        
        if ($tokenAge.Days -gt 30) {
            Write-Host "⚠️  Warning: Authentication token is old, may need refresh"
        }
    } else {
        Write-Host "⚠️  Warning: No authentication token found"
    }
    
    # Check 8: Scheduled Tasks
    Write-Host "`n⏰ Checking scheduled tasks..."
    $tasks = @("GoogleDriveSync-Full", "GoogleDriveSync-Incremental", "GoogleDriveSync-Resume", "GoogleDriveSync-HealthCheck")
    
    foreach ($taskName in $tasks) {
        try {
            $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
            $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction Stop
            
            $status = if ($task.State -eq "Ready") { "✅" } else { "⚠️ " }
            Write-Host "$status Task: $taskName - State: $($task.State), Last Run: $($taskInfo.LastRunTime)"
            
            if ($taskInfo.LastTaskResult -ne 0 -and $taskInfo.LastRunTime) {
                Write-Host "   ⚠️  Last run result: $($taskInfo.LastTaskResult)"
            }
        } catch {
            Write-Host "❌ Task not found: $taskName"
        }
    }
    
    # Summary
    Write-Host "`n" + "=" * 60
    if ($exitCode -eq 1) {
        Write-Host "❌ Health Check FAILED - Issues detected"
        Write-Host "📧 Consider sending alert to administrator"
    } else {
        Write-Host "✅ Health Check PASSED - System operating normally"
    }
    Write-Host "🕐 Check completed at $(Get-Date)"
    Write-Host "=" * 60
    
    # Log to Windows Event Log (optional)
    try {
        $source = "GoogleDriveSync"
        if (-not [System.Diagnostics.EventLog]::SourceExists($source)) {
            New-EventLog -LogName Application -Source $source
        }
        
        $eventType = if ($exitCode -eq 0) { "Information" } else { "Warning" }
        $message = "Health check completed with exit code $exitCode. Check logs for details."
        
        Write-EventLog -LogName Application -Source $source -EventId 1000 -EntryType $eventType -Message $message
    } catch {
        # Ignore if can't write to event log
    }
    
    exit $exitCode
    
} catch {
    Write-Host "❌ Health check script failed: $($_.Exception.Message)"
    Write-Host "📧 Critical error - immediate attention required"
    exit 2
}