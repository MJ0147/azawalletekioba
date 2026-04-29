param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$Location,

    [Parameter(Mandatory = $true)]
    [string]$DockerUsername,

    [Parameter(Mandatory = $true)]
    [SecureString]$DockerPassword,

    [Parameter(Mandatory = $true)]
    [string]$BackendAppName,

    [Parameter(Mandatory = $true)]
    [string]$FrontendAppName,

    [string]$ServicePrincipalName = "github-actions",
    [string]$AppServicePlanName = "ekioba-linux-plan",
    [string]$BackendImage = "backend:latest",
    [string]$FrontendImage = "frontend:latest"
)

$ErrorActionPreference = "Stop"

function Test-AzCliInstalled {
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw "Azure CLI is not installed or not in PATH."
    }
}

function Test-AzureLoginSession {
    try {
        az account show --output none
    }
    catch {
        throw "Not logged in. Run 'az login' with your enterprise account first."
    }
}

Test-AzCliInstalled
Test-AzureLoginSession

$dockerPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($DockerPassword)
)

Write-Host "Setting Azure subscription context..." -ForegroundColor Cyan
az account set --subscription $SubscriptionId

Write-Host "Ensuring resource group exists..." -ForegroundColor Cyan
az group create --name $ResourceGroup --location $Location --output table

Write-Host "Creating or updating App Service plan (Linux)..." -ForegroundColor Cyan
az appservice plan create `
    --name $AppServicePlanName `
    --resource-group $ResourceGroup `
    --location $Location `
    --is-linux `
    --sku B1 `
    --output table

$backendImageRef = "docker.io/$DockerUsername/$BackendImage"
$frontendImageRef = "docker.io/$DockerUsername/$FrontendImage"

Write-Host "Creating backend web app..." -ForegroundColor Cyan
az webapp create `
    --resource-group $ResourceGroup `
    --plan $AppServicePlanName `
    --name $BackendAppName `
    --deployment-container-image-name $backendImageRef `
    --output table

Write-Host "Creating frontend web app..." -ForegroundColor Cyan
az webapp create `
    --resource-group $ResourceGroup `
    --plan $AppServicePlanName `
    --name $FrontendAppName `
    --deployment-container-image-name $frontendImageRef `
    --output table

Write-Host "Configuring backend DockerHub pull settings..." -ForegroundColor Cyan
az webapp config container set `
    --name $BackendAppName `
    --resource-group $ResourceGroup `
    --docker-custom-image-name $backendImageRef `
    --docker-registry-server-url https://index.docker.io `
    --docker-registry-server-user $DockerUsername `
    --docker-registry-server-password $dockerPasswordPlain `
    --output table

Write-Host "Configuring frontend DockerHub pull settings..." -ForegroundColor Cyan
az webapp config container set `
    --name $FrontendAppName `
    --resource-group $ResourceGroup `
    --docker-custom-image-name $frontendImageRef `
    --docker-registry-server-url https://index.docker.io `
    --docker-registry-server-user $DockerUsername `
    --docker-registry-server-password $dockerPasswordPlain `
    --output table

Write-Host "Setting frontend container port to 3000..." -ForegroundColor Cyan
az webapp config appsettings set `
    --name $FrontendAppName `
    --resource-group $ResourceGroup `
    --settings WEBSITES_PORT=3000 `
    --output table

Write-Host "Creating service principal for GitHub Actions..." -ForegroundColor Cyan
$spJson = az ad sp create-for-rbac `
    --name $ServicePrincipalName `
    --role contributor `
    --scopes /subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup `
    --sdk-auth

$spPath = Join-Path (Get-Location) "azure-credentials.json"
$spJson | Out-File -FilePath $spPath -Encoding utf8 -Force

Write-Host "Done. Add these GitHub repository secrets:" -ForegroundColor Green
Write-Host "  AZURE_CREDENTIALS  -> contents of $spPath" -ForegroundColor Yellow
Write-Host "  DOCKER_USERNAME    -> $DockerUsername" -ForegroundColor Yellow
Write-Host "  DOCKER_PASSWORD    -> <your DockerHub password or token>" -ForegroundColor Yellow
Write-Host "  AZURE_BACKEND_APP  -> $BackendAppName" -ForegroundColor Yellow
Write-Host "  AZURE_FRONTEND_APP -> $FrontendAppName" -ForegroundColor Yellow

Write-Host "Backend URL:" -ForegroundColor Green
az webapp show --name $BackendAppName --resource-group $ResourceGroup --query defaultHostName -o tsv

Write-Host "Frontend URL:" -ForegroundColor Green
az webapp show --name $FrontendAppName --resource-group $ResourceGroup --query defaultHostName -o tsv

$dockerPasswordPlain = $null
