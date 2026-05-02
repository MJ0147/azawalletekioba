# EKIOBA

EKIOBA is a multi-service workspace containing the storefront, cargo, hotels, language academy, AI assistant, and frontend applications.

## Deployment model

Local Docker build scripts are no longer part of the supported workflow. Deployments should run through GitHub Actions so builds and releases happen in CI instead of from a local Docker environment.

Primary workflows:

- `.github/workflows/ci.yml` validates backend and frontend on pull requests and pushes.
- `.github/workflows/azure-pipeline.yml` is the single deployment pipeline targeting Azure Web Apps.

## Working locally

Run services with their native runtimes for development and testing. Do not rely on the removed root Docker build scripts for local setup or deployment.

## Deployment prerequisites

Configure the required GitHub repository secrets and variables for the target workflow before merging to `main` or triggering a manual deployment.

See `DEPLOYMENT.md` for deployment-specific notes and required secrets.
