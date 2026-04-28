# Ekioba Kubernetes Deployment Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| kubectl | ≥ 1.25 | Cluster management |
| helm | ≥ 3.x | Package manager (optional) |
| cert-manager | ≥ 1.13 | TLS certificate automation |
| ingress-nginx | ≥ 1.9 | Ingress controller |
| metrics-server | ≥ 0.6 | HPA metrics source |

## Directory Structure

```
k8s/
├── namespace.yaml                    # ekioba namespace with PSS labels
├── secrets.example.yaml              # Secret template (copy → secrets.yaml)
├── app-config-configmap.yaml         # Application configuration
├── nginx-custom-headers-configmap.yaml # Ingress proxy headers
├── ingress-main.yaml                 # Frontend + AI Assistant ingress
├── ingress-api.yaml                  # /api/* route rewrites
├── ingress-rules.yaml                # Annotations reference (comments only)
├── hpa.yaml                          # HorizontalPodAutoscalers (all 6 services)
├── pdb.yaml                          # PodDisruptionBudgets
├── network-policy.yaml               # NetworkPolicies
├── pod-security-policy.yaml          # PSP (k8s ≤ 1.24) / PSS labels (≥ 1.25)
├── cert-manager/
│   └── cluster-issuer.yaml           # Let's Encrypt prod + staging ClusterIssuers
├── store/
│   ├── deployment.yaml
│   └── service.yaml
├── cargo/
│   ├── deployment.yaml
│   └── service.yaml
├── hotels/
│   ├── deployment.yaml
│   └── service.yaml
├── language-academy/
│   ├── deployment.yaml
│   └── service.yaml
├── ai-assistant/
│   ├── deployment.yaml
│   └── service.yaml
└── frontend/
    ├── deployment.yaml
    └── service.yaml
```

## Step-by-Step Deployment

### 1. Install cluster prerequisites

```bash
# cert-manager (pin to a specific version for reproducibility)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.5/cert-manager.yaml
kubectl wait --for=condition=Available deployment --all -n cert-manager --timeout=120s

# metrics-server (for HPA)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.7.1/components.yaml

# ingress-nginx (if not already installed)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/cloud/deploy.yaml
kubectl wait --for=condition=Available deployment ingress-nginx-controller -n ingress-nginx --timeout=120s
```

### 2. Create namespace and apply infrastructure policies

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/pod-security-policy.yaml
kubectl apply -f k8s/network-policy.yaml
```

### 3. Configure secrets

> **IMPORTANT:** Never commit `k8s/secrets.yaml` to version control.
> It is already listed in `.gitignore`.

```bash
cp k8s/secrets.example.yaml k8s/secrets.yaml
# Edit k8s/secrets.yaml and replace all REPLACE_WITH_* values
kubectl apply -f k8s/secrets.yaml
```

### 4. Apply ConfigMaps

```bash
kubectl apply -f k8s/app-config-configmap.yaml
kubectl apply -f k8s/nginx-custom-headers-configmap.yaml
```

### 5. Install cert-manager ClusterIssuers

> Use **staging** first to avoid Let's Encrypt rate limits.

```bash
# Update the email address in k8s/cert-manager/cluster-issuer.yaml first!
kubectl apply -f k8s/cert-manager/cluster-issuer.yaml

# Verify issuers are ready
kubectl get clusterissuer
```

### 6. Deploy services

Before applying, update each `deployment.yaml` to reference your actual
container image tags from your registry:

```bash
# Example: replace placeholder image tags
# image: store:latest  →  image: your-registry/ekioba-store:1.0.0

kubectl apply -f k8s/store/
kubectl apply -f k8s/cargo/
kubectl apply -f k8s/hotels/
kubectl apply -f k8s/language-academy/
kubectl apply -f k8s/ai-assistant/
kubectl apply -f k8s/frontend/

# Wait for all pods to be running
kubectl rollout status deployment --all -n ekioba --timeout=180s
```

### 7. Apply Ingress (use staging TLS first!)

Edit `k8s/ingress-main.yaml` and `k8s/ingress-api.yaml`:
- Replace `ekioba.example.com` with your actual domain
- Set `cert-manager.io/cluster-issuer: "letsencrypt-staging"` initially

```bash
kubectl apply -f k8s/ingress-main.yaml
kubectl apply -f k8s/ingress-api.yaml

# Watch for TLS certificate issuance
kubectl get certificate -n ekioba -w
```

Once staging certificates are working, switch to production:

```bash
# Update both ingress files: letsencrypt-staging → letsencrypt-prod
kubectl apply -f k8s/ingress-main.yaml
kubectl apply -f k8s/ingress-api.yaml
```

### 8. Enable autoscaling and resilience

```bash
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/pdb.yaml

# Verify HPAs are active (TARGETS should show real metrics after ~1 min)
kubectl get hpa -n ekioba
```

## Verification Checklist

```bash
# All pods running
kubectl get pods -n ekioba

# Services reachable
kubectl get svc -n ekioba

# Ingress status (external IP assigned)
kubectl get ingress -n ekioba

# TLS certificate issued
kubectl describe certificate ekioba-tls -n ekioba

# HPA targets populated
kubectl get hpa -n ekioba

# Pod disruption budgets active
kubectl get pdb -n ekioba
```

## Image Registry Setup

Before deploying to production, build and push images to your registry:

```bash
# Example using Docker Hub
docker build -t yourregistry/ekioba-store:1.0.0 ./store
docker push yourregistry/ekioba-store:1.0.0

# Repeat for each service: cargo, hotels, language-academy, ai-assistant, frontend
```

Then update each `deployment.yaml` image field accordingly.

## Updating Secrets

```bash
# Edit the values
kubectl edit secret ekioba-secrets -n ekioba

# Or recreate from template
kubectl delete secret ekioba-secrets -n ekioba
kubectl apply -f k8s/secrets.yaml

# Restart deployments to pick up new secret values
kubectl rollout restart deployment --all -n ekioba
```

## Rolling Updates

```bash
# Update a specific service image
kubectl set image deployment/store store=yourregistry/ekioba-store:1.1.0 -n ekioba

# Monitor the rollout
kubectl rollout status deployment/store -n ekioba

# Roll back if needed
kubectl rollout undo deployment/store -n ekioba
```
