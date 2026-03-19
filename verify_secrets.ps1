# Script to verify Secret Manager permissions for the default Cloud Run service account

$ErrorActionPreference = "Stop"
$PROJECT_ID = (gcloud config get-value project).Trim()

if (-not $PROJECT_ID) {
    Write-Error "No GCP Project ID set. Run: gcloud config set project <YOUR_PROJECT_ID>"
    exit 1
}

$SERVICE_ACCOUNT_NAME = "ekioba-identity"
# Custom Identity Service Account
$SERVICE_ACCOUNT = "$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

Write-Host "------------------------------------------------"
Write-Host "Verifying Secret Manager Permissions"
Write-Host "Project: $PROJECT_ID"
Write-Host "Service Account: $SERVICE_ACCOUNT"
Write-Host "------------------------------------------------"

$SECRETS = @(
    "TON_API_KEY", 
    "SOLANA_RPC_URL", 
    "DJANGO_SECRET_KEY", 
    "COCKROACHDB_STORE_URL", 
    "COCKROACHDB_HOTELS_URL"
)

$allPassed = $true

foreach ($SECRET in $SECRETS) {
    Write-Host -NoNewline "Checking $SECRET ... "
    
    try {
        # Check if secret exists first
        gcloud secrets describe $SECRET --project $PROJECT_ID --quiet > $null 2>&1
        if (-not $?) {
            Write-Host "[MISSING]" -ForegroundColor Red
            Write-Host "  -> Secret '$SECRET' does not exist in project."
            $allPassed = $false
            continue
        }

        # Get IAM policy
        $json = gcloud secrets get-iam-policy $SECRET --project $PROJECT_ID --format="json" | Out-String
        $policy = $json | ConvertFrom-Json
        
        $hasAccess = $false
        if ($policy.bindings) {
            foreach ($binding in $policy.bindings) {
                if ($binding.role -eq "roles/secretmanager.secretAccessor") {
                    foreach ($member in $binding.members) {
                        if ($member -eq "serviceAccount:$SERVICE_ACCOUNT") {
                            $hasAccess = $true
                            break
                        }
                    }
                }
                if ($hasAccess) { break }
            }
        }

        if ($hasAccess) {
            Write-Host "[OK]" -ForegroundColor Green
        } else {
            Write-Host "[FAILED]" -ForegroundColor Red
            Write-Host "  -> Service account is missing 'roles/secretmanager.secretAccessor'."
            $allPassed = $false
        }
    }
    catch {
        Write-Host "[ERROR]" -ForegroundColor Red
        Write-Host "  -> $_"
        $allPassed = $false
    }
}

Write-Host "------------------------------------------------"
if ($allPassed) {
    Write-Host "Verification PASSED. Service account has access to all secrets." -ForegroundColor Green
} else {
    Write-Host "Verification FAILED. Some secrets are missing or inaccessible." -ForegroundColor Red
    Write-Host "Run './deploy_ekioba.ps1' to attempt automatic repair."
}