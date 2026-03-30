param(
    [Parameter(Mandatory = $true)]
    [string]$Client,
    [Parameter(Mandatory = $false)]
    [ValidateSet("dev", "prod")]
    [string]$Environment = "prod"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $backendDir
$targetRelativePath = "backend-integration/clients/$Client/$Environment.tfvars"
$sharedRelativePath = "backend-integration/clients/$Client/terraform.tfvars"
$secretKeys = @(
    "stripe_secret_key",
    "stripe_webhook_secret",
    "textbelt_api_key",
    "detailer_phone_number",
    "calcom_webhook_secret"
)

function ConvertFrom-TfvarsContent {
    param(
        [string]$Content
    )

    $result = @{}
    foreach ($line in ($Content -split "`r?`n")) {
        if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*"([^"]*)"\s*$') {
            $result[$matches[1]] = $matches[2]
        }
    }

    return $result
}

function Get-TfvarsMap {
    param(
        [string]$RelativePath
    )

    $absolutePath = Join-Path $repoRoot $RelativePath
    $content = ""
    if (Test-Path -LiteralPath $absolutePath) {
        $content = Get-Content -LiteralPath $absolutePath -Raw
    }

    $map = ConvertFrom-TfvarsContent -Content $content
    $hasPlainSecrets = $false
    foreach ($key in $secretKeys) {
        $value = $map[$key]
        if ($value -and -not $value.StartsWith("/tra3/") -and $value -notmatch 'REPLACE|example|placeholder') {
            $hasPlainSecrets = $true
            break
        }
    }

    if ($hasPlainSecrets) {
        return $map
    }

    $gitPath = $RelativePath.Replace("\", "/")
    $headContent = ((@(& git show "HEAD:$gitPath" 2>$null)) -join "`n")
    if ($LASTEXITCODE -ne 0 -or -not $headContent) {
        return $map
    }

    return ConvertFrom-TfvarsContent -Content $headContent
}

function Get-SecretValue {
    param(
        [hashtable]$PrimaryMap,
        [hashtable]$FallbackMap,
        [string]$Key
    )

    $value = $PrimaryMap[$Key]
    if (-not $value) {
        $value = $FallbackMap[$Key]
    }

    if (-not $value) {
        return $null
    }

    if ($value.StartsWith("/tra3/") -or $value -match 'REPLACE|example|placeholder') {
        return $null
    }

    return $value
}

$environmentMap = Get-TfvarsMap -RelativePath $targetRelativePath
$sharedMap = Get-TfvarsMap -RelativePath $sharedRelativePath
$awsRegion = $environmentMap["aws_region"]
if (-not $awsRegion) {
    $awsRegion = $sharedMap["aws_region"]
}
if (-not $awsRegion) {
    $awsRegion = "us-east-1"
}

foreach ($key in $secretKeys) {
    $value = Get-SecretValue -PrimaryMap $environmentMap -FallbackMap $sharedMap -Key $key
    if (-not $value) {
        Write-Host "Skipping $key - no plaintext value found in working tree or HEAD." -ForegroundColor Yellow
        continue
    }

    $parameterName = "/tra3/$Client/$Environment/$key"
    & aws ssm put-parameter --region $awsRegion --name $parameterName --type SecureString --value $value --overwrite
    if ($LASTEXITCODE -ne 0) {
        throw "aws ssm put-parameter failed for $parameterName"
    }

    Write-Host "Stored $parameterName" -ForegroundColor Green
}

Write-Host ""
Write-Host "Migration finished." -ForegroundColor Green
Write-Host "Next step: run .\\backend-integration\\scripts\\deploy.ps1 -Client $Client -Environment $Environment" -ForegroundColor White
