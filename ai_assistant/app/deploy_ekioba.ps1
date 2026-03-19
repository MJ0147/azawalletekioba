# Ekioba Cloud Run Deployment Script
#
# This script deploys all EKIOBA services to Google Cloud Run.
# It assumes you have an Artifact Registry repository named 'ekioba' in your project.
# If not, create one with:
# gcloud artifacts repositories create ekioba --repository-format=docker --location=us-central1

$PROJECT_ID = gcloud config get-value project
$REGION = "us-central1" # Deployment region

if (-not $PROJECT_ID) {
    Write-Error "No GCP Project ID set. Please run 'gcloud config set project <YOUR_PROJECT_ID>' first."
    exit 1
}

# Fix: Ensure script runs from project root so relative paths (./store, ./frontend) work
Write-Host "Setting working directory to project root..."
Set-Location "$PSScriptRoot/../.."

# Fix: Ensure ADC quota project matches current project to prevent warnings
Write-Host "Syncing ADC quota project..."
gcloud auth application-default set-quota-project $PROJECT_ID 2>$null

Write-Host "------------------------------------------------"
Write-Host "Deploying Ekioba to Project: $PROJECT_ID"
Write-Host "Region: $REGION"
Write-Host "------------------------------------------------"

# 1.1 Grant Secret Accessor Roles
Write-Host "Granting secret accessor permissions to runtime service account..."
$SERVICE_ACCOUNT_NAME = "ekioba-identity"
$SERVICE_ACCOUNT = "$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

# Check if service account exists, create if not
gcloud iam service-accounts describe $SERVICE_ACCOUNT --project $PROJECT_ID --quiet > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "--> Creating service account: $SERVICE_ACCOUNT"
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME --display-name "Ekioba Runtime Identity" --project $PROJECT_ID
}

$SECRETS = @("TON_API_KEY", "SOLANA_RPC_URL", "DJANGO_SECRET_KEY", "COCKROACHDB_STORE_URL", "COCKROACHDB_HOTELS_URL")

foreach ($SECRET in $SECRETS) {
    Write-Host "--> Granting access to $SECRET..."
    gcloud secrets add-iam-policy-binding $SECRET --member="serviceAccount:$SERVICE_ACCOUNT" --role="roles/secretmanager.secretAccessor" --quiet | Out-Null
}

# 2. Deploy Backend Services
Write-Host "`n[2/5] Deploying all backend services..."
Write-Host "This will mount secrets from Google Secret Manager as environment variables."

# Deploy AI Assistant (Iyobo)
Write-Host "--> Deploying AI Assistant (ekioba-ai-assistant)..."
$IYOBO_URL = gcloud run deploy ekioba-ai-assistant `
    --source ./ai_assistant `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --service-account $SERVICE_ACCOUNT `
    --set-secrets "TON_API_KEY=TON_API_KEY:latest" `
    --format "value(status.url)"

if (-not $IYOBO_URL) { Write-Error "Failed to deploy AI Assistant. Aborting."; exit 1 }
Write-Host "    Success: AI Assistant live at $IYOBO_URL"

# Deploy Store Service
Write-Host "--> Deploying Store (ekioba-store)..."
$STORE_URL = gcloud run deploy ekioba-store `
    --source ./store `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --service-account $SERVICE_ACCOUNT `
    --set-secrets "DJANGO_SECRET_KEY=DJANGO_SECRET_KEY:latest,COCKROACHDB_URL=COCKROACHDB_STORE_URL:latest,SOLANA_RPC_URL=SOLANA_RPC_URL:latest,TON_API_KEY=TON_API_KEY:latest" `
    --format "value(status.url)"

if (-not $STORE_URL) { Write-Error "Failed to deploy Store service. Aborting."; exit 1 }
Write-Host "    Success: Store service live at $STORE_URL"

# Deploy other backend microservices
Write-Host "--> Deploying cargo (ekioba-cargo)..."
gcloud run deploy "ekioba-cargo" --source "./cargo" --region $REGION --platform managed --allow-unauthenticated --service-account $SERVICE_ACCOUNT

Write-Host "--> Deploying hotels (ekioba-hotels)..."
gcloud run deploy "ekioba-hotels" `
    --source "./hotels" `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --service-account $SERVICE_ACCOUNT `
    --set-secrets "DJANGO_SECRET_KEY=DJANGO_SECRET_KEY:latest,COCKROACHDB_URL=COCKROACHDB_HOTELS_URL:latest"

Write-Host "--> Deploying language_academy (ekioba-language-academy)..."
gcloud run deploy "ekioba-language-academy" --source "./language_academy" --region $REGION --platform managed --allow-unauthenticated --service-account $SERVICE_ACCOUNT

# 3. Build Frontend with Backend URLs
Write-Host "`n[3/5] Building frontend with backend service URLs..."
$IYOBO_CHAT_URL = "$IYOBO_URL/chat"
$STORE_API_URL = "$STORE_URL/api/products/"
Write-Host "--> Injecting NEXT_PUBLIC_IYOBO_URL=$IYOBO_CHAT_URL"
Write-Host "--> Injecting NEXT_PUBLIC_STORE_PRODUCTS_URL=$STORE_API_URL"

$frontend_image = "${REGION}-docker.pkg.dev/$PROJECT_ID/ekioba/ekioba-frontend"
$cloudbuild_content = @"
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '--build-arg', 'NEXT_PUBLIC_IYOBO_URL=$IYOBO_CHAT_URL', '--build-arg', 'NEXT_PUBLIC_STORE_PRODUCTS_URL=$STORE_API_URL', '-t', '$frontend_image', '.']
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', '$frontend_image']
images:
- '$frontend_image'
"@

Set-Content -Path "cloudbuild_frontend_temp.yaml" -Value $cloudbuild_content -Encoding UTF8
gcloud builds submit ./frontend --config cloudbuild_frontend_temp.yaml
Remove-Item "cloudbuild_frontend_temp.yaml"

# 4. Deploy Frontend
Write-Host "`n[4/5] Deploying frontend..."
gcloud run deploy ekioba-frontend `
    --image $frontend_image `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --service-account $SERVICE_ACCOUNT

# 5. Summary
Write-Host "`n[5/5] DEPLOYMENT COMPLETE"
Write-Host "------------------------------------------------"
Write-Host "Frontend is live at:"
gcloud run services describe ekioba-frontend --region $REGION --format "value(status.url)"
Write-Host "------------------------------------------------"