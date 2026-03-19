# Script to deploy ONLY the EKIOBA Frontend
# Useful for rapid UI updates without redeploying the backend/universal stack.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-GCloudCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args,

        [Parameter(Mandatory = $true)]
        [string]$FailureMessage,

        [switch]$CaptureOutput
    )

    if ($CaptureOutput) {
        $output = & gcloud @Args 2>&1
        if ($LASTEXITCODE -eq 0) {
            return ($output | Out-String).Trim()
        }
        throw $FailureMessage
    }

    & gcloud @Args
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

$PROJECT_ID = (gcloud config get-value project).Trim()
$REGION = "us-central1"
$SERVICE_NAME = "ekioba-frontend"
$REPO_NAME = "ekioba"

# Ensure consistent relative paths regardless of where the script is launched from.
Set-Location "$PSScriptRoot"

if (-not $PROJECT_ID) {
    Write-Error "No GCP Project ID set. Run: gcloud config set project <YOUR_PROJECT_ID>"
    exit 1
}

# Fix: Ensure script runs from project root
if (Test-Path "$PSScriptRoot/frontend") {
    Write-Host "Setting working directory to: $PSScriptRoot"
    Set-Location "$PSScriptRoot"
}

Write-Host "------------------------------------------------"
Write-Host "Deploying Ekioba Frontend Only"
Write-Host "Project: $PROJECT_ID"
Write-Host "Region: $REGION"
Write-Host "------------------------------------------------"

# 1. Determine Backend URLs for Environment Variables
Write-Host "`n[1/3] resolving backend URLs..."

# Manual override from user request
$MANUAL_BACKEND_URL = "https://python-api-653036098161.us-central1.run.app"

# Try to find the Universal service URL first (preferred architecture)
$UNIVERSAL_URL = (gcloud run services describe ekioba-universal --region $REGION --project $PROJECT_ID --format "value(status.url)" 2>$null)

if ($MANUAL_BACKEND_URL) {
    Write-Host "--> Using Manual Backend Service: $MANUAL_BACKEND_URL"
    $NEXT_PUBLIC_IYOBO_URL = "$MANUAL_BACKEND_URL/chat"
    $NEXT_PUBLIC_STORE_PRODUCTS_URL = "$MANUAL_BACKEND_URL/api/store/products/"
    $NEXT_PUBLIC_BACKEND_URL = "$MANUAL_BACKEND_URL"
} elseif ($UNIVERSAL_URL) {
    Write-Host "--> Found Universal Service: $UNIVERSAL_URL"
    $NEXT_PUBLIC_IYOBO_URL = "$UNIVERSAL_URL/chat"
    $NEXT_PUBLIC_STORE_PRODUCTS_URL = "$UNIVERSAL_URL/api/store/products/"
    $NEXT_PUBLIC_BACKEND_URL = "$UNIVERSAL_URL"
} else {
    # Fallback to looking for individual microservices
    Write-Host "--> Universal service not found. Looking for individual services..."
    $IYOBO_RAW = (gcloud run services describe ekioba-ai-assistant --region $REGION --project $PROJECT_ID --format "value(status.url)" 2>$null)
    $STORE_RAW = (gcloud run services describe ekioba-store --region $REGION --project $PROJECT_ID --format "value(status.url)" 2>$null)
    
    if ($IYOBO_RAW) { $NEXT_PUBLIC_IYOBO_URL = "$IYOBO_RAW/chat" } else { $NEXT_PUBLIC_IYOBO_URL = "" }
    if ($STORE_RAW) { 
        $NEXT_PUBLIC_STORE_PRODUCTS_URL = "$STORE_RAW/api/products/" 
        $NEXT_PUBLIC_BACKEND_URL = "$STORE_RAW"
    } else { 
        $NEXT_PUBLIC_STORE_PRODUCTS_URL = "" 
        $NEXT_PUBLIC_BACKEND_URL = ""
    }
}

Write-Host "   > NEXT_PUBLIC_IYOBO_URL: $NEXT_PUBLIC_IYOBO_URL"
Write-Host "   > NEXT_PUBLIC_STORE_PRODUCTS_URL: $NEXT_PUBLIC_STORE_PRODUCTS_URL"
Write-Host "   > NEXT_PUBLIC_BACKEND_URL: $NEXT_PUBLIC_BACKEND_URL"

# 2. Build the Frontend Container
Write-Host "`n[2/3] Building Frontend Container..."
$IMAGE_TAG = (Get-Date -Format "yyyyMMdd-HHmmss")
$IMAGE = "${REGION}-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/ekioba-frontend:$IMAGE_TAG"

# Ensure lockfiles exist in the frontend directory for the build context
if (Test-Path "package-lock.json") {
    Write-Host "Syncing package-lock.json to frontend build context..."
    Copy-Item "package-lock.json" -Destination "frontend/package-lock.json" -Force
}
if (Test-Path "yarn.lock") {
    Write-Host "Syncing yarn.lock to frontend build context..."
    Copy-Item "yarn.lock" -Destination "frontend/yarn.lock" -Force
}

# Ensure Artifact Registry repository exists before pushing image.
& gcloud artifacts repositories describe $REPO_NAME --location=$REGION --project=$PROJECT_ID > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "--> Creating Artifact Registry repository: $REPO_NAME"
    Invoke-GCloudCommand -Args @(
        "artifacts", "repositories", "create", $REPO_NAME,
        "--repository-format=docker",
        "--location=$REGION",
        "--description=Ekioba Container Registry",
        "--project=$PROJECT_ID"
    ) -FailureMessage "Failed to create Artifact Registry repository '$REPO_NAME'."
}

# Verify Dockerfile exists before submitting
if (-not (Test-Path "./frontend/Dockerfile")) {
    Write-Error "Dockerfile not found in ./frontend. Please check your directory structure."
    exit 1
}

# Using a temporary cloudbuild config to inject build args dynamically
$cloudbuild_content = @"
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '--build-arg', 'NEXT_PUBLIC_IYOBO_URL=$NEXT_PUBLIC_IYOBO_URL', '--build-arg', 'NEXT_PUBLIC_STORE_PRODUCTS_URL=$NEXT_PUBLIC_STORE_PRODUCTS_URL', '--build-arg', 'NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL', '-t', '$IMAGE', '.']
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', '$IMAGE']
images:
- '$IMAGE'
"@

$CB_FILE = "cloudbuild_frontend_temp.yaml"
Set-Content -Path $CB_FILE -Value $cloudbuild_content -Encoding UTF8

try {
    # Submit build from the frontend directory
    Invoke-GCloudCommand -Args @("builds", "submit", "./frontend", "--config", $CB_FILE, "--project", $PROJECT_ID) -FailureMessage "Frontend build failed: image was not created/pushed."
}
finally {
    if (Test-Path $CB_FILE) { Remove-Item $CB_FILE }
}

# 3. Deploy to Cloud Run
Write-Host "`n[3/3] Deploying to Cloud Run ($SERVICE_NAME)..."
$SERVICE_ACCOUNT = "ekioba-identity@$PROJECT_ID.iam.gserviceaccount.com"

Invoke-GCloudCommand -Args @(
    "run", "deploy", $SERVICE_NAME,
    "--image", $IMAGE,
    "--region", $REGION,
    "--project", $PROJECT_ID,
    "--service-account", $SERVICE_ACCOUNT,
    "--platform", "managed",
    "--allow-unauthenticated",
    "--memory", "1Gi"
) -FailureMessage "Frontend deployment failed."

Write-Host "`n------------------------------------------------"
Write-Host "Frontend Deployment Complete!"
Write-Host "------------------------------------------------"