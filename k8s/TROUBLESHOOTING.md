# Ekioba Kubernetes Troubleshooting Guide

## Pod Issues

### Pods stuck in `Pending`

```bash
kubectl describe pod <pod-name> -n ekioba
```

**Common causes:**
- **Insufficient resources** — check node capacity: `kubectl describe nodes`
- **PVC not bound** — check persistent volume claims: `kubectl get pvc -n ekioba`
- **Image pull failure** — verify registry credentials and image tag exist
- **Node selector / affinity mismatch** — remove or adjust `nodeSelector`

---

### Pods stuck in `CrashLoopBackOff`

```bash
# Check logs
kubectl logs <pod-name> -n ekioba --previous

# Check events
kubectl describe pod <pod-name> -n ekioba
```

**Common causes:**
- **Readiness/liveness probe failing** — the app may not yet expose `/health/`.
  Temporarily increase `initialDelaySeconds` to 120 while debugging.
- **Missing secret key** — ensure `k8s/secrets.yaml` has all required keys and is applied.
- **Read-only filesystem error** — app writing to a path not mounted as `emptyDir`.
  Add an `emptyDir` volume for the path.
- **Permission denied** — app trying to bind port < 1024 or write to system dirs.

---

### Pods in `OOMKilled`

The container hit its memory limit. Increase the limit in `deployment.yaml`:

```yaml
resources:
  limits:
    memory: "1Gi"  # increase from 512Mi
```

---

### `Init container` keeps looping

The `wait-for-db` init container can't reach CockroachDB.

```bash
kubectl logs <pod-name> -c wait-for-db -n ekioba
```

- Check the database hostname in the init container env vars (`DB_HOST`).
- Verify the database service is running and reachable from the `ekioba` namespace.

---

## Ingress / TLS Issues

### `404` on all routes

```bash
kubectl get ingress -n ekioba
kubectl describe ingress ekioba-main -n ekioba
```

- Verify `ingressClassName: nginx` matches your ingress controller class.
- Check that the ingress controller pod is running: `kubectl get pods -n ingress-nginx`

---

### TLS certificate not issued / stuck in `Pending`

```bash
kubectl get certificate -n ekioba
kubectl describe certificaterequest -n ekioba
kubectl describe challenge -n ekioba
```

**Common causes:**
- **Rate limit hit** — switch to `letsencrypt-staging` issuer and retry.
- **ACME HTTP-01 challenge failing** — the domain must resolve to the cluster's external IP.
  Check: `nslookup ekioba.example.com` and `kubectl get svc -n ingress-nginx`.
- **cert-manager not running** — `kubectl get pods -n cert-manager`

---

### `502 Bad Gateway` on API routes

The ingress can reach the backend but the backend returned an error.

```bash
kubectl logs deployment/store -n ekioba
kubectl logs deployment/hotels -n ekioba
```

Also verify rewrite rules are correct — confirm the `rewrite-target` regex captures the right group.

---

### WebSocket connections dropping

Ensure the following annotations are present on the relevant Ingress:

```yaml
nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
```

And in the configuration snippet:

```yaml
nginx.ingress.kubernetes.io/configuration-snippet: |
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
```

---

## HPA Issues

### HPA shows `<unknown>` for metrics

```bash
kubectl describe hpa -n ekioba
```

- Metrics server may not be installed or running: `kubectl get pods -n kube-system | grep metrics-server`
- Pods must have CPU `requests` set (already configured in our deployments).
- Wait ~1-2 minutes after deployment for metrics to populate.

---

### HPA not scaling up

- Check current replica count vs max: `kubectl get hpa -n ekioba`
- Confirm pod CPU requests are set (HPA needs them to calculate utilization).
- Check for PDB blocking scale-up: `kubectl get pdb -n ekioba`

---

## Secret / Config Issues

### `secret "ekioba-secrets" not found`

```bash
# Verify the secret exists
kubectl get secret ekioba-secrets -n ekioba

# Recreate it from the template
cp k8s/secrets.example.yaml k8s/secrets.yaml
# fill in real values, then:
kubectl apply -f k8s/secrets.yaml
```

### Environment variable not updated after secret change

```bash
# Restart all pods to pick up the new values
kubectl rollout restart deployment --all -n ekioba
```

---

## Network Policy Issues

### Pod can't reach external APIs (Solana/TON)

The `allow-egress-all` policy permits all outbound traffic. If it was removed or modified,
re-apply the network-policy file:

```bash
kubectl apply -f k8s/network-policy.yaml
```

### Pods can't communicate with each other

Verify each service NetworkPolicy allows traffic from `app.kubernetes.io/part-of: ekioba`.
Cross-service calls go through the internal ClusterIP service DNS names.

---

## Useful Debug Commands

```bash
# Exec into a pod for manual inspection
kubectl exec -it deployment/store -n ekioba -- /bin/sh

# Test internal DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -n ekioba -- \
  nslookup store-svc.ekioba.svc.cluster.local

# Check resource usage
kubectl top pods -n ekioba
kubectl top nodes

# Get all events sorted by time
kubectl get events -n ekioba --sort-by='.lastTimestamp'

# Full pod description (includes events, mounts, env vars)
kubectl describe pod <pod-name> -n ekioba
```
