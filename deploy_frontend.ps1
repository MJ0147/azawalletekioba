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

# 1. Determine Backend URLs for Frontend FastAPI Environment Variables
Write-Host "`n[1/3] resolving backend URLs..."

# Manual override from user request
$MANUAL_BACKEND_URL = "https://python-api-653036098161.us-central1.run.app"

# Try to find the Universal service URL first (preferred architecture)
$UNIVERSAL_URL = (gcloud run services describe ekioba-universal --region $REGION --project $PROJECT_ID --format "value(status.url)" 2>$null)

if ($MANUAL_BACKEND_URL) {
    Write-Host "--> Using Manual Backend Service: $MANUAL_BACKEND_URL"
    $STORE_BACKEND_URL = "$MANUAL_BACKEND_URL/api/store/products/"
    $STORE_PAYMENTS_URL = "$MANUAL_BACKEND_URL/payments/process/"
    $AI_ASSISTANT_URL = "$MANUAL_BACKEND_URL"
    $FRONTEND_IYOBO_URL = "/chat"
} elseif ($UNIVERSAL_URL) {
    Write-Host "--> Found Universal Service: $UNIVERSAL_URL"
    $STORE_BACKEND_URL = "$UNIVERSAL_URL/api/store/products/"
    $STORE_PAYMENTS_URL = "$UNIVERSAL_URL/payments/process/"
    $AI_ASSISTANT_URL = "$UNIVERSAL_URL"
    $FRONTEND_IYOBO_URL = "/chat"
} else {
    # Fallback to looking for individual microservices
    Write-Host "--> Universal service not found. Looking for individual services..."
    $IYOBO_RAW = (gcloud run services describe ekioba-ai-assistant --region $REGION --project $PROJECT_ID --format "value(status.url)" 2>$null)
    $STORE_RAW = (gcloud run services describe ekioba-store --region $REGION --project $PROJECT_ID --format "value(status.url)" 2>$null)
    
    if ($IYOBO_RAW) {
        $AI_ASSISTANT_URL = "$IYOBO_RAW"
        $FRONTEND_IYOBO_URL = "/chat"
    } else {
        $AI_ASSISTANT_URL = ""
        $FRONTEND_IYOBO_URL = "/chat"
    }
    if ($STORE_RAW) { 
        $STORE_BACKEND_URL = "$STORE_RAW/api/products/"
        $STORE_PAYMENTS_URL = "$STORE_RAW/payments/process/"
    } else { 
        $STORE_BACKEND_URL = ""
        $STORE_PAYMENTS_URL = ""
    }
}

Write-Host "   > STORE_BACKEND_URL: $STORE_BACKEND_URL"
Write-Host "   > STORE_PAYMENTS_URL: $STORE_PAYMENTS_URL"
Write-Host "   > AI_ASSISTANT_URL: $AI_ASSISTANT_URL"
Write-Host "   > FRONTEND_IYOBO_URL: $FRONTEND_IYOBO_URL"

# 2. Build the Frontend Container
Write-Host "`n[2/3] Building Frontend Container..."
$IMAGE_TAG = (Get-Date -Format "yyyyMMdd-HHmmss")
$IMAGE = "${REGION}-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/ekioba-frontend:$IMAGE_TAG"

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

# Submit build from the frontend directory (Python FastAPI image)
Invoke-GCloudCommand -Args @("builds", "submit", "./frontend", "--tag", $IMAGE, "--project", $PROJECT_ID) -FailureMessage "Frontend build failed: image was not created/pushed."

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
    "--memory", "1Gi",
    "--set-env-vars", "STORE_BACKEND_URL=$STORE_BACKEND_URL,STORE_PAYMENTS_URL=$STORE_PAYMENTS_URL,AI_ASSISTANT_URL=$AI_ASSISTANT_URL,FRONTEND_IYOBO_URL=$FRONTEND_IYOBO_URL"
) -FailureMessage "Frontend deployment failed."

Write-Host "`n------------------------------------------------"
Write-Host "Frontend Deployment Complete!"
Write-Host "------------------------------------------------"