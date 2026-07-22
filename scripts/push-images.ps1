param(
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvPath = Join-Path $Root $EnvFile

if (-not (Test-Path -LiteralPath $EnvPath)) {
    throw "Env file not found: $EnvPath. Copy .env.example to .env and fill registry settings first."
}

$Values = @{}
Get-Content -LiteralPath $EnvPath | ForEach-Object {
    $Line = $_.Trim()
    if ($Line -eq "" -or $Line.StartsWith("#")) {
        return
    }
    $Index = $Line.IndexOf("=")
    if ($Index -lt 1) {
        return
    }
    $Key = $Line.Substring(0, $Index).Trim()
    $Value = $Line.Substring($Index + 1).Trim().Trim('"')
    $Values[$Key] = $Value
}

foreach ($Required in @("REGISTRY", "IMAGE_NAMESPACE", "VERSION")) {
    if (-not $Values.ContainsKey($Required) -or [string]::IsNullOrWhiteSpace($Values[$Required])) {
        throw "Env file is missing $Required"
    }
}

$Registry = $Values["REGISTRY"].TrimEnd("/")
$Namespace = $Values["IMAGE_NAMESPACE"].Trim("/")
$Version = $Values["VERSION"]
$FrontendImage = "$Registry/$Namespace/baby-education-frontend:$Version"
$BackendImage = "$Registry/$Namespace/baby-education-backend:$Version"

if ($Values["REGISTRY_USERNAME"] -and $Values["REGISTRY_PASSWORD"]) {
    Write-Host "Logging in to registry $Registry"
    $Values["REGISTRY_PASSWORD"] | docker login $Registry -u $Values["REGISTRY_USERNAME"] --password-stdin
}

Write-Host "Building frontend image $FrontendImage"
docker build -f (Join-Path $Root "frontend/Dockerfile") -t $FrontendImage (Join-Path $Root "frontend")

Write-Host "Building backend image $BackendImage"
docker build -f (Join-Path $Root "backend/Dockerfile") -t $BackendImage (Join-Path $Root "backend")

Write-Host "Pushing frontend image"
docker push $FrontendImage

Write-Host "Pushing backend image"
docker push $BackendImage

Write-Host "Done. On the deploy host, copy docker-compose.yml and .env, then run: docker compose --env-file .env up -d"
