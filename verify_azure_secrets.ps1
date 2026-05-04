<#
.SYNOPSIS
    Verifies all required Azure Key Vault secrets exist for EKIOBA deployment.
.DESCRIPTION
    Checks that every secret needed by the application is present in Azure Key Vault.
    Reports missing secrets without exposing their values.
.PARAMETER KeyVaultName
    Name of the Azure Key Vault (e.g. ekioba-kv)
.EXAMPLE
    .\verify_azure_secrets.ps1 -KeyVaultName "ekioba-kv"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$KeyVaultName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Required secrets for all services
$RequiredSecrets = @(
    # Azure SQL Managed Instance
    "AZURE-SQL-HOST",
    "AZURE-SQL-PORT",
    "AZURE-SQL-USER",
    "AZURE-SQL-PASSWORD",
    "AZURE-SQL-STORE-DB",
    "AZURE-SQL-HOTELS-DB",

    # Django / App
    "DJANGO-SECRET-KEY",
    "JWT-SECRET",

    # TON Blockchain
    "TONPAY-API-KEY",
    "TON-API-KEY",
    "STORE-WALLET-ADDRESS",
    "TON-CONTRACT-ADDRESS",

    # AI / APIs
    "GEMINI-API-KEY",
    "GOOGLE-GENAI-API-KEY",

    # Telegram
    "TELEGRAM-BOT-TOKEN",

    # Container Registry
    "DOCKERHUB-TOKEN",

    # Redis
    "REDIS-URL"
)

Write-Host "`n=== EKIOBA Azure Key Vault Secret Verification ===" -ForegroundColor Cyan
Write-Host "Key Vault: $KeyVaultName`n"

$missing = @()
$found = 0

foreach ($secret in $RequiredSecrets) {
    try {
        $result = az keyvault secret show --vault-name $KeyVaultName --name $secret --query "name" -o tsv 2>$null
        if ($result -eq $secret) {
            Write-Host "  [OK]     $secret" -ForegroundColor Green
            $found++
        } else {
            Write-Host "  [MISSING] $secret" -ForegroundColor Red
            $missing += $secret
        }
    } catch {
        Write-Host "  [MISSING] $secret" -ForegroundColor Red
        $missing += $secret
    }
}

Write-Host ""
Write-Host "Found:   $found / $($RequiredSecrets.Count)" -ForegroundColor $(if ($missing.Count -eq 0) { "Green" } else { "Yellow" })

if ($missing.Count -gt 0) {
    Write-Host "Missing: $($missing.Count) secret(s)" -ForegroundColor Red
    Write-Host "`nTo create a missing secret:" -ForegroundColor Cyan
    Write-Host "  az keyvault secret set --vault-name $KeyVaultName --name <SECRET-NAME> --value '<value>'"
    exit 1
} else {
    Write-Host "`nAll secrets verified. Ready for deployment." -ForegroundColor Green
    exit 0
}
