# Azure Live Connection Ready

This repository is now prepared for:
- Docker image build and push on main branch
- Azure Web App for Containers deployment from GitHub Actions

## What is already wired

- Workflow: .github/workflows/deploy.yml
- Trigger: push to main and manual workflow dispatch
- Build output: DockerHub images tagged with latest and commit SHA
- Deployment target: two Azure Linux Web Apps using commit SHA image tags

## Run once after enterprise Azure login

1. Login and verify:

   az login
   az account show

2. Execute provisioning script:

    $dockerPass = Read-Host "DockerHub password or access token" -AsSecureString
    ./prepare_azure_live_connection.ps1 `
       -SubscriptionId <SUB_ID> `
       -ResourceGroup <RG_NAME> `
       -Location <AZURE_REGION> `
       -DockerUsername <DOCKERHUB_USERNAME> `
       -DockerPassword $dockerPass `
       -BackendAppName <UNIQUE_BACKEND_APP_NAME> `
       -FrontendAppName <UNIQUE_FRONTEND_APP_NAME>

The script will:
- Create resource group if missing
- Create Linux App Service plan
- Create both Web Apps for containers
- Configure DockerHub pull credentials on both apps
- Set frontend WEBSITES_PORT=3000
- Create service principal and save AZURE_CREDENTIALS JSON in azure-credentials.json

## Add these GitHub repository secrets

- AZURE_CREDENTIALS (content of azure-credentials.json)
- DOCKER_USERNAME
- DOCKER_PASSWORD
- AZURE_BACKEND_APP
- AZURE_FRONTEND_APP

## Validation

After secrets are added:
- Push any commit to main
- Open Actions tab and confirm CI/CD Pipeline run succeeds
- Confirm both web apps are updated to image tag matching the commit SHA
