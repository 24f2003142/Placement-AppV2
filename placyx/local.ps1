Write-Host "Starting Placyx Placement App..."

# Step 1: Create virtual environment if missing
function Test-PythonCommand {
    param([string]$command)
    try {
        $output = & $command --version 2>&1
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

$pythonCmd = $null
$pythonArgs = @()
if (Test-PythonCommand python) {
    $pythonCmd = "python"
} elseif (Test-PythonCommand py) {
    $pythonCmd = "py"
    $pythonArgs = @("-3")
} elseif (Test-PythonCommand python3) {
    $pythonCmd = "python3"
}

if (-not $pythonCmd) {
    Write-Host "ERROR: Python is not available as a valid executable. Install Python 3 and make sure it is on your PATH." -ForegroundColor Red
    exit 1
}

if (-Not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    if ($pythonArgs.Count -gt 0) {
        & $pythonCmd @pythonArgs -m venv venv
    } else {
        & $pythonCmd -m venv venv
    }
    if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
}

# Step 2: Activate virtual environment
.\venv\Scripts\Activate.ps1

# Step 3: Upgrade pip
pip install --upgrade pip

# Step 4: Install dependencies
pip install -r requirements.txt

function Wait-ForRedis {
    param(
        [int]$TimeoutSeconds = 30
    )

    $endTime = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $endTime) {
        $connection = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue
        if ($connection.TcpTestSucceeded) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

# Step 5: Configure Celery environment
$env:CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
$env:DAILY_REMINDER_HOUR = "23"
$env:DAILY_REMINDER_MINUTE = "50"
# Optional: set your GChat webhook URL here if configured
$env:GCHAT_WEBHOOK_URL = ""

# SMTP environment variables (example values for SMTP2GO). Set SMTP_USER and SMTP_PASS to real credentials.
$env:SMTP_HOST = "mail-eu.smtp2go.com"
$env:SMTP_PORT = "2525"
# $env:SMTP_USER = "your_smtp_username"
# $env:SMTP_PASS = "your_smtp_password"
$env:SMTP_FROM = "no-reply@placyx.com"
$env:SMTP_USE_TLS = "true"

# Ensure Redis is available for Celery
$redisReady = (Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue).TcpTestSucceeded
if (-not $redisReady) {
    Write-Host "Redis is not reachable on localhost:6379. Attempting to start Redis..."

    if (-not (Get-Command redis-server -ErrorAction SilentlyContinue)) {
        if (Get-Command scoop -ErrorAction SilentlyContinue) {
            Write-Host "Installing Redis via Scoop..."
            scoop install redis
        } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
            Write-Host "Installing Redis via Chocolatey..."
            choco install redis-64 -y
        } elseif (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "Installing Redis via winget..."
            winget install --id Redis.Redis -e --accept-package-agreements --accept-source-agreements
        }
    }

    $redisServerCmd = Get-Command redis-server -ErrorAction SilentlyContinue
    if (-not $redisServerCmd) {
        $possiblePaths = @(
            "$env:ProgramFiles\Redis\redis-server.exe",
            "$env:ProgramFiles(x86)\Redis\redis-server.exe",
            "C:\Program Files\Redis\redis-server.exe",
            "C:\Program Files (x86)\Redis\redis-server.exe"
        )
        foreach ($path in $possiblePaths) {
            if (Test-Path $path) {
                $redisServerCmd = $path
                break
            }
        }
    }

    if ($redisServerCmd) {
        Write-Host "Launching local redis-server..."
        Start-Process -NoNewWindow -FilePath $redisServerCmd
    } elseif (Get-Command docker -ErrorAction SilentlyContinue) {
        $containerName = "placyx-redis"
        $existingContainer = docker ps -aq -f "name=^${containerName}$"
        if ($existingContainer) {
            $isRunning = docker ps -q -f "name=^${containerName}$"
            if (-not $isRunning) {
                Write-Host "Starting existing Redis container: $containerName"
                docker start $containerName | Out-Null
            } else {
                Write-Host "Redis container $containerName is already running."
            }
        } else {
            Write-Host "Creating and starting Redis container: $containerName"
            docker run -d --name $containerName -p 6379:6379 redis | Out-Null
        }
    } elseif (Get-Command wsl -ErrorAction SilentlyContinue) {
        Write-Host "Attempting to start Redis inside WSL..."
        $distros = wsl.exe -l -q 2>$null
        if ($distros) {
            $wslCommand = 'bash -lc "command -v redis-server >/dev/null 2>&1 && redis-server --port 6379 --daemonize yes"'
            try {
                wsl.exe $wslCommand | Out-Null
                Write-Host "WSL Redis start command issued."
            } catch {
                Write-Host "ERROR: Unable to start Redis inside WSL." -ForegroundColor Red
                Write-Host "Install Redis inside WSL or use Docker/Windows Redis installation."
                exit 1
            }
        } else {
            Write-Host "ERROR: WSL is available but no Linux distribution is installed." -ForegroundColor Red
            Write-Host "Install Redis using Windows Redis or Docker, then rerun ./local.ps1."
            exit 1
        }
    } else {
        Write-Host "ERROR: Redis is not running and could not be installed or started on this machine." -ForegroundColor Red
        Write-Host "Install Redis, Docker, or WSL with Redis and run ./local.ps1 again."
        exit 1
    }

    if (-not (Wait-ForRedis -TimeoutSeconds 30)) {
        Write-Host "ERROR: Redis did not become available within 30 seconds." -ForegroundColor Red
        Write-Host "Check the Redis installation, Docker container, or WSL Redis logs, then retry."
        exit 1
    }

    Write-Host "Redis is available on localhost:6379."
}

# Step 6: Run Flask app, Celery worker, and Celery beat
$pythonExe = if (Test-Path "venv\Scripts\python.exe") { Join-Path $PWD "venv\Scripts\python.exe" } else { $pythonCmd }

Start-Process -FilePath $pythonExe -ArgumentList "app.py"
Start-Process -FilePath $pythonExe -ArgumentList @("-m", "celery", "-A", "celery_app.celery", "worker", "--loglevel=info", "--pool=solo")
Start-Process -FilePath $pythonExe -ArgumentList @("-m", "celery", "-A", "celery_app.celery", "beat", "--loglevel=info")

# Step 7: Open browser
Start-Sleep -Seconds 1
Start-Process "http://127.0.0.1:5000"
