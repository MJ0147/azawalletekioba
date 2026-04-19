param(
	[Parameter(Mandatory = $false)]
	[string]$Repository = "azawalletekioba/ekioba",

	[Parameter(Mandatory = $false)]
	[string]$SourceTag = "latest",

	[Parameter(Mandatory = $false)]
	[string]$Tag = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-DockerCommand {
	param(
		[Parameter(Mandatory = $true)]
		[string[]]$Args,

		[Parameter(Mandatory = $true)]
		[string]$FailureMessage
	)

	& docker @Args
	if ($LASTEXITCODE -ne 0) {
		throw $FailureMessage
	}
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
	throw "Docker CLI is not installed or not available in PATH."
}

$currentContext = ""
try {
	$currentContext = (& docker context show 2>$null | Out-String).Trim()
}
catch {
	$currentContext = ""
}

if ($currentContext -eq "desktop-linux") {
	Write-Warning "Current Docker context is 'desktop-linux'. Continuing with active context."
}

& docker version *> $null
if ($LASTEXITCODE -ne 0) {
	throw "Docker engine is not reachable. Restart Docker Desktop and run 'docker version' until it succeeds."
}

$timestampTag = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
if ([string]::IsNullOrWhiteSpace($Tag)) {
	$Tag = "build-$timestampTag"
}

$sourceImage = "${Repository}:${SourceTag}"
$image = "${Repository}:${Tag}"

Write-Host "Checking local Docker image: $sourceImage"
& docker image inspect $sourceImage *> $null
if ($LASTEXITCODE -ne 0) {
	throw "Local image '$sourceImage' does not exist. Build or tag it first, then rerun this script."
}

if ($sourceImage -ne $image) {
	Write-Host "Tagging image: $sourceImage -> $image"
	Invoke-DockerCommand -Args @("tag", $sourceImage, $image) -FailureMessage "Failed to tag '$sourceImage' as '$image'."
}

Write-Host "Pushing Docker image: $image"
Invoke-DockerCommand -Args @("push", $image) -FailureMessage "Failed to push Docker image '$image'. Ensure you are logged in to Docker Hub and have permission to push to this repository."

$repoDigests = (& docker image inspect $image --format "{{join .RepoDigests \"`n\"}}" | Out-String).Trim() -split "`r?`n"
$publishedDigest = $repoDigests | Where-Object { $_ -like "$Repository@*" } | Select-Object -First 1

Write-Host "Push complete: $image"
if (-not [string]::IsNullOrWhiteSpace($publishedDigest)) {
	Write-Host "Published digest: $publishedDigest"
}
else {
	Write-Warning "Could not resolve pushed digest from local metadata."
}
