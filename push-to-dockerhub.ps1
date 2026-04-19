# EKIOBA Docker Push Script
# Run this to push EKIOBA images to Docker Hub

param(
    [Parameter(Mandatory = $false)]
    [string]$Repository = "azawalletekioba/ekioba",

    [Parameter(Mandatory = $false)]
    [string]$Tag = "latest"
)

$image = "${Repository}:${Tag}"

Write-Host "=== Pushing EKIOBA to Docker Hub ===" -ForegroundColor Green

# Check if Docker is running
try {
    & docker --version | Out-Null
} catch {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Login to Docker Hub
Write-Host "Logging in to Docker Hub..." -ForegroundColor Cyan
& docker login -u azawalletekioba
if ($LASTEXITCODE -ne 0) {
    Write-Host "Login failed. Please check your credentials." -ForegroundColor Red
    exit 1
}

# List available images
Write-Host "Available images:" -ForegroundColor Yellow
& docker images

# Tag and push images
Write-Host "Tagging and pushing images..." -ForegroundColor Cyan

# If you have specific images, tag them
# Example: docker tag <image-id> $image

# Push the main image
Write-Host "Pushing image: $image" -ForegroundColor Yellow
& docker push $image
if ($LASTEXITCODE -ne 0) {
    Write-Host "Push failed. Check image name and registry access." -ForegroundColor Red
    exit 1
}

Write-Host "=== Push Complete ===" -ForegroundColor Green
Write-Host "Image pushed to: https://hub.docker.com/r/azawalletekioba/ekioba/tags" -ForegroundColor Green