# Ekioba Universal Cloud Run Deployment Script
#
# This script builds one universal image (Dockerfile.universal)
# and deploys a single Cloud Run service: ekioba-universal.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-GCloudCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args,

        [Parameter(Mandatory = $true)]
        [string]$FailureMessage,

        [int]$Retries = 1,
        [int]$BaseDelaySeconds = 10,
        [switch]$CaptureOutput
    )

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        if ($CaptureOutput) {
            $output = & gcloud @Args 2>&1
            if ($LASTEXITCODE -eq 0) {
                return ($output | Out-String).Trim()
            }
        }
        else {
            & gcloud @Args
            if ($LASTEXITCODE -eq 0) {
                return
            }
        }

        if ($attempt -lt $Retries) {
            $delaySeconds = $BaseDelaySeconds * $attempt
            Write-Warning "$FailureMessage Retry $attempt/$Retries failed. Waiting $delaySeconds seconds before retry..."
            Start-Sleep -Seconds $delaySeconds
        }
    }

    throw $FailureMessage
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud CLI is not installed or not available in PATH."
}

$PROJECT_ID = (& gcloud config get-value project 2>$null | Out-String).Trim()
$REGION = "us-central1"
$SERVICE_NAME = "ekioba-universal"
$REPOSITORY = "ekioba"

if (-not $PROJECT_ID -or $PROJECT_ID -eq "(unset)") {
    throw "No GCP Project ID set. Run: gcloud config set project <YOUR_PROJECT_ID>"
}

$IMAGE = "${REGION}-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME"

# Ensure script runs from repository root where Dockerfile.universal exists.
Write-Host "Setting working directory to repository root..."
Set-Location "$PSScriptRoot"

Write-Host "Syncing ADC quota project..."
gcloud auth application-default set-quota-project $PROJECT_ID 2>$null

Write-Host "------------------------------------------------"
Write-Host "Deploying Ekioba Universal"
Write-Host "Project: $PROJECT_ID"
Write-Host "Region: $REGION"
Write-Host "Service: $SERVICE_NAME"
Write-Host "------------------------------------------------"

Write-Host "`n[0/4] Ensuring Artifact Registry '$REPOSITORY' exists..."
& gcloud artifacts repositories describe $REPOSITORY --location=$REGION --project=$PROJECT_ID > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "--> Creating Artifact Registry repository: $REPOSITORY"
    Invoke-GCloudCommand -Args @("artifacts", "repositories", "create", $REPOSITORY, "--repository-format=docker", "--location=$REGION", "--description=Ekioba Container Registry", "--project=$PROJECT_ID") -FailureMessage "Failed to create Artifact Registry repository '$REPOSITORY'."
}

Write-Host "`n[1/4] Enabling required Google Cloud APIs..."
Invoke-GCloudCommand -Args @("services", "enable", "run.googleapis.com", "artifactregistry.googleapis.com", "cloudbuild.googleapis.com", "secretmanager.googleapis.com", "cloudresourcemanager.googleapis.com", "--project=$PROJECT_ID") -FailureMessage "Failed to enable required Google Cloud APIs." -Retries 3 -BaseDelaySeconds 15

Write-Host "`n[2/4] Granting secret access to runtime service account..."
$SERVICE_ACCOUNT_NAME = "ekioba-identity"
$SERVICE_ACCOUNT = "$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

# Check if service account exists, create if not
gcloud iam service-accounts describe $SERVICE_ACCOUNT --project $PROJECT_ID --quiet > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "--> Creating service account: $SERVICE_ACCOUNT"
    Invoke-GCloudCommand -Args @("iam", "service-accounts", "create", $SERVICE_ACCOUNT_NAME, "--display-name=Ekioba Runtime Identity", "--project=$PROJECT_ID") -FailureMessage "Failed to create service account '$SERVICE_ACCOUNT'."
}

$SECRETS = @("TON_API_KEY", "SOLANA_RPC_URL", "DJANGO_SECRET_KEY", "AZURE_SQL_HOST", "AZURE_SQL_USER", "AZURE_SQL_PASSWORD")
$MISSING_SECRETS = @()

foreach ($SECRET in $SECRETS) {
    & gcloud secrets describe $SECRET --project=$PROJECT_ID > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        $MISSING_SECRETS += $SECRET
    }
}

if ($MISSING_SECRETS.Count -gt 0) {
    throw "Missing required secrets in project '$PROJECT_ID': $($MISSING_SECRETS -join ', ')."
}

foreach ($SECRET in $SECRETS) {
    Write-Host "--> Granting access to $SECRET"
    Invoke-GCloudCommand -Args @("secrets", "add-iam-policy-binding", $SECRET, "--member=serviceAccount:$SERVICE_ACCOUNT", "--role=roles/secretmanager.secretAccessor", "--project=$PROJECT_ID", "--quiet") -FailureMessage "Failed to grant '$SECRET' access to '$SERVICE_ACCOUNT'."
}

Write-Host "`n[3/4] Building and pushing universal image..."
if (-not (Test-Path "cloudbuild.universal.yaml")) {
    throw "Missing required file: cloudbuild.universal.yaml"
}
$buildSubstitutions = @(
    "_IMAGE=$IMAGE",
    "_NEXT_PUBLIC_IYOBO_URL=/chat",
    "_NEXT_PUBLIC_STORE_PRODUCTS_URL=/api/store/products/",
    "_NEXT_PUBLIC_BACKEND_URL=/api"
) -join ","

Invoke-GCloudCommand -Args @("builds", "submit", ".", "--config", "cloudbuild.universal.yaml", "--substitutions", $buildSubstitutions, "--project=$PROJECT_ID") -FailureMessage "Build failed after retries: image was not created/pushed." -Retries 3 -BaseDelaySeconds 20

Write-Host "`n[4/4] Deploying Cloud Run service '$SERVICE_NAME'..."
$SERVICE_URL = Invoke-GCloudCommand -Args @(
    "run", "deploy", $SERVICE_NAME,
    "--image", $IMAGE,
    "--region", $REGION,
    "--project", $PROJECT_ID,
    "--service-account", $SERVICE_ACCOUNT,
    "--platform", "managed",
    "--allow-unauthenticated",
    "--port", "8080",
    "--cpu", "2",
    "--memory", "2Gi",
    "--concurrency", "20",
    "--timeout", "300",
    # NOTE: :latest refers to GCP Secret Manager secret VERSION (not Docker tag).
    # This is correct — Secret Manager uses version syntax :latest, :previous, or explicit version IDs.
    "--set-secrets", "DJANGO_SECRET_KEY=DJANGO_SECRET_KEY:latest,SOLANA_RPC_URL=SOLANA_RPC_URL:latest,TON_API_KEY=TON_API_KEY:latest,AZURE_SQL_HOST=AZURE_SQL_HOST:latest,AZURE_SQL_USER=AZURE_SQL_USER:latest,AZURE_SQL_PASSWORD=AZURE_SQL_PASSWORD:latest",
    "--set-env-vars", "NEXT_PUBLIC_IYOBO_URL=/chat,NEXT_PUBLIC_STORE_PRODUCTS_URL=/api/store/products/,STORE_PAYMENTS_URL=http://127.0.0.1:8000/payments/process/",
    "--format", "value(status.url)"
) -FailureMessage "Deployment failed: Cloud Run deploy command did not succeed." -CaptureOutput

$SERVICE_URL = $SERVICE_URL.Trim()

if (-not $SERVICE_URL) {
    throw "Deployment failed: Cloud Run did not return a service URL."
}

$CANONICAL_URL = Invoke-GCloudCommand -Args @("run", "services", "describe", $SERVICE_NAME, "--region", $REGION, "--project", $PROJECT_ID, "--format", "value(status.url)") -FailureMessage "Failed to fetch canonical Cloud Run service URL." -CaptureOutput
$CANONICAL_URL = $CANONICAL_URL.Trim()
if (-not $CANONICAL_URL) {
    $CANONICAL_URL = $SERVICE_URL
}

Write-Host "`nDEPLOYMENT COMPLETE"
Write-Host "------------------------------------------------"
Write-Host "Universal service is live at:"
Write-Host $CANONICAL_URL
Write-Host "------------------------------------------------"