# EKIOBA Project Setup and Docker Deploy Script
# Run this script to install dependencies and push to Docker Hub

Write-Host "=== EKIOBA Project Setup ===" -ForegroundColor Green

# Check Node version
$nodeVersion = & node --version
Write-Host "Node version: $nodeVersion" -ForegroundColor Yellow
if ($nodeVersion -match "v24") {
    Write-Host "WARNING: Node v24 detected. Next.js 14 requires <24. Please install Node 23 from https://nodejs.org" -ForegroundColor Red
    exit 1
}

# Install frontend dependencies
Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
Set-Location frontend
& npm ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Set-Location ..

# Install backend dependencies
Write-Host "Installing ai_assistant dependencies..." -ForegroundColor Cyan
Set-Location ai_assistant
& pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Set-Location ..

# Check other services
Write-Host "Installing cargo dependencies..." -ForegroundColor Cyan
Set-Location cargo
& pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Set-Location ..

Write-Host "Installing hotels dependencies..." -ForegroundColor Cyan
Set-Location hotels
& python manage.py migrate --run-syncdb
Set-Location ..

# Build Docker images
Write-Host "Building Docker images..." -ForegroundColor Cyan
& docker-compose build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Login to Docker Hub (user needs to provide credentials)
Write-Host "Please login to Docker Hub:" -ForegroundColor Yellow
& docker login
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Push images
Write-Host "Pushing images to Docker Hub..." -ForegroundColor Cyan
& docker-compose push
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Images pushed to Docker Hub successfully!" -ForegroundColor Green