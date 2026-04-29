# ─────────────────────────────────────────────────────────────────────────────
# build-and-push.ps1
#
# Builds and pushes all EKIOBA service Docker images to Docker Hub.
# Run from the repo root: .\build-and-push.ps1
#
# Optional flags:
#   -Tag        Image tag (default: latest)
#   -Registry   Docker Hub username/org (default: azawalletekioba)
#   -Services   Comma-separated subset, e.g. "store,frontend" (default: all)
#   -NoPush     Build only, skip docker push
# ─────────────────────────────────────────────────────────────────────────────
param(
    [string]$Tag      = "latest",
    [string]$Registry = "azawalletekioba",
    [string]$Services = "store,cargo,hotels,language-academy,ai-assistant,frontend",
    [switch]$NoPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── service definitions ───────────────────────────────────────────────────────
# name        : Docker Hub image suffix  (ekioba-<name>)
# context     : build context directory relative to repo root
# dockerfile  : Dockerfile path relative to repo root
# buildArgs   : optional --build-arg pairs as hashtable
$allServices = @(
    @{ name = "store";            context = "store";            dockerfile = "store\Dockerfile";            buildArgs = @{} }
    @{ name = "cargo";            context = "cargo";            dockerfile = "cargo\Dockerfile";            buildArgs = @{} }
    @{ name = "hotels";           context = "hotels";           dockerfile = "hotels\Dockerfile";           buildArgs = @{} }
    @{ name = "language-academy"; context = "language_academy"; dockerfile = "language_academy\Dockerfile"; buildArgs = @{} }
    @{ name = "ai-assistant";     context = "ai_assistant";     dockerfile = "ai_assistant\Dockerfile";     buildArgs = @{} }
    @{ name = "frontend";         context = "frontend";         dockerfile = "frontend\Dockerfile";         buildArgs = @{} }
)

# ── helpers ───────────────────────────────────────────────────────────────────
function Write-Step([string]$msg) {
    Write-Host "`n━━━ $msg" -ForegroundColor Cyan
}
function Write-Ok([string]$msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}
function Write-Fail([string]$msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
}

# ── preflight: docker daemon healthy? ────────────────────────────────────────
Write-Step "Checking Docker daemon"
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker daemon is not responding. Start Docker Desktop and retry."
    Write-Host $dockerInfo -ForegroundColor DarkGray
    exit 1
}
Write-Ok "Docker daemon is healthy"

# ── preflight: logged in? ─────────────────────────────────────────────────────
Write-Step "Checking Docker Hub login"
$whoami = docker info 2>&1 | Select-String "Username:"
if (-not $whoami) {
    Write-Host "  Not logged in — running docker login..." -ForegroundColor Yellow
    docker login
    if ($LASTEXITCODE -ne 0) { Write-Fail "Login failed"; exit 1 }
}
Write-Ok "Logged in to Docker Hub"

# ── filter requested services ─────────────────────────────────────────────────
$requested = $Services.Split(",") | ForEach-Object { $_.Trim().ToLower() }
$toBuild   = $allServices | Where-Object { $requested -contains $_.name }
if ($toBuild.Count -eq 0) {
    Write-Fail "No matching services found. Valid names: $($allServices.name -join ', ')"
    exit 1
}

# ── build + push loop ─────────────────────────────────────────────────────────
$results = @()
$startTime = Get-Date

foreach ($svc in $toBuild) {
    $image = "$Registry/ekioba-$($svc.name):$Tag"
    Write-Step "[$($svc.name)]  →  $image"

    # Resolve paths
    $contextPath    = Join-Path $PSScriptRoot $svc.context
    $dockerfilePath = Join-Path $PSScriptRoot $svc.dockerfile

    if (-not (Test-Path $contextPath)) {
        Write-Fail "Build context not found: $contextPath"; $results += @{ name=$svc.name; status="FAILED (no context)" }; continue
    }
    if (-not (Test-Path $dockerfilePath)) {
        Write-Fail "Dockerfile not found: $dockerfilePath"; $results += @{ name=$svc.name; status="FAILED (no Dockerfile)" }; continue
    }

    # Build arg string
    $buildArgStr = ($svc.buildArgs.GetEnumerator() | ForEach-Object { "--build-arg $($_.Key)=$($_.Value)" }) -join " "

    # ── BUILD ────────────────────────────────────────────────────────────────
    Write-Host "  Building..." -ForegroundColor DarkGray
    $buildCmd = "docker build -t $image -f `"$dockerfilePath`" $buildArgStr `"$contextPath`""
    Write-Host "  $buildCmd" -ForegroundColor DarkGray
    Invoke-Expression $buildCmd

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Build failed for $($svc.name)"
        $results += @{ name=$svc.name; status="BUILD FAILED" }
        continue
    }
    Write-Ok "Build successful → $image"

    # ── PUSH ─────────────────────────────────────────────────────────────────
    if (-not $NoPush) {
        Write-Host "  Pushing..." -ForegroundColor DarkGray
        docker push $image

        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Push failed for $($svc.name)"
            $results += @{ name=$svc.name; status="PUSH FAILED" }
            continue
        }
        Write-Ok "Pushed → $image"
        $results += @{ name=$svc.name; status="OK" }
    } else {
        $results += @{ name=$svc.name; status="BUILT (push skipped)" }
    }
}

# ── summary ───────────────────────────────────────────────────────────────────
$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds)
Write-Step "Summary  (${elapsed}s total)"
foreach ($r in $results) {
    $color = if ($r.status -eq "OK" -or $r.status -like "BUILT*") { "Green" } else { "Red" }
    Write-Host ("  {0,-20} {1}" -f $r.name, $r.status) -ForegroundColor $color
}

$failed = $results | Where-Object { $_.status -notmatch "^(OK|BUILT)" }
if ($failed.Count -gt 0) {
    Write-Host "`nSome services failed. Fix errors above and re-run." -ForegroundColor Red
    exit 1
}

Write-Host "`nAll images ready. Deploy with:" -ForegroundColor Green
Write-Host "  kubectl apply -f k8s/namespace.yaml" -ForegroundColor DarkGray
Write-Host "  kubectl apply -f k8s/secrets.yaml" -ForegroundColor DarkGray
Write-Host "  kubectl apply -f k8s/nginx-custom-headers-configmap.yaml" -ForegroundColor DarkGray
Write-Host "  kubectl apply -f k8s/store/ -f k8s/cargo/ -f k8s/hotels/ -f k8s/language-academy/ -f k8s/ai-assistant/ -f k8s/frontend/" -ForegroundColor DarkGray
Write-Host "  kubectl apply -f k8s/ingress-main.yaml -f k8s/ingress-api.yaml -f k8s/hpa.yaml" -ForegroundColor DarkGray
