Write-Host "Starting Placyx Placement App..."

# Step 1: Create virtual environment if missing
if (-Not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

# Step 2: Activate virtual environment
.\venv\Scripts\Activate.ps1

# Step 3: Upgrade pip
pip install --upgrade pip

# Step 4: Install dependencies
pip install -r requirements.txt

# Step 5: Run Flask app
Start-Process python app.py

# Step 6: Open browser
Start-Sleep -Seconds 10
Start-Process "http://127.0.0.1:5000"
