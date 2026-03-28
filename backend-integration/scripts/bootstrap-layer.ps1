param()

$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param(
        [string]$Action
    )

    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed with exit code $LASTEXITCODE."
    }
}

function Remove-PathIfExists {
    param(
        [string]$Path,
        [switch]$Recurse
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    if ($Recurse) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    else {
        Remove-Item -LiteralPath $Path -Force
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $backendDir
$layerDir = Join-Path $backendDir "layer"
$buildDir = Join-Path $layerDir "layer-build"
$pythonDir = Join-Path $buildDir "python"
$requirementsFile = Join-Path $layerDir "requirements.txt"
$layerZip = Join-Path $layerDir "layer.zip"
$encryptionConfigFile = Join-Path $layerDir "bucket-encryption.json"
$publicAccessBlockFile = Join-Path $layerDir "bucket-public-access.json"
$region = "us-east-1"
$encryptionConfig = @{
    Rules = @(
        @{
            ApplyServerSideEncryptionByDefault = @{
                SSEAlgorithm = "AES256"
            }
        }
    )
} | ConvertTo-Json -Compress -Depth 5
$publicAccessBlock = @{
    BlockPublicAcls       = $true
    IgnorePublicAcls      = $true
    BlockPublicPolicy     = $true
    RestrictPublicBuckets = $true
} | ConvertTo-Json -Compress

Set-Location $repoRoot

try {
    Write-Host "=== TRA3 Layer Bootstrap ===" -ForegroundColor Cyan

    $accountId = ((@(& aws sts get-caller-identity --query Account --output text)) -join "").Trim()
    Assert-LastExitCode "aws sts get-caller-identity"

    $s3Bucket = "tra3-$accountId-deployments"
    $s3Key = "layers/dependencies/layer.zip"

    Write-Host "Step 1 - Ensure deployment bucket exists" -ForegroundColor Cyan
    $existingBucket = ((@(& aws s3api list-buckets --query "Buckets[?Name=='$s3Bucket'].Name" --output text)) -join "").Trim()
    Assert-LastExitCode "aws s3api list-buckets"
    if (-not $existingBucket) {
        if ($region -eq "us-east-1") {
            & aws s3api create-bucket --bucket $s3Bucket
        }
        else {
            & aws s3api create-bucket --bucket $s3Bucket --create-bucket-configuration "LocationConstraint=$region"
        }
        Assert-LastExitCode "aws s3api create-bucket"
    }

    Set-Content -LiteralPath $encryptionConfigFile -Value $encryptionConfig -Encoding ascii
    Set-Content -LiteralPath $publicAccessBlockFile -Value $publicAccessBlock -Encoding ascii

    & aws s3api put-bucket-versioning --bucket $s3Bucket --versioning-configuration Status=Enabled
    Assert-LastExitCode "aws s3api put-bucket-versioning"
    & aws s3api put-bucket-encryption --bucket $s3Bucket --server-side-encryption-configuration "file://$encryptionConfigFile"
    Assert-LastExitCode "aws s3api put-bucket-encryption"
    & aws s3api put-public-access-block --bucket $s3Bucket --public-access-block-configuration "file://$publicAccessBlockFile"
    Assert-LastExitCode "aws s3api put-public-access-block"

    Write-Host "Step 2 - Build dependency layer" -ForegroundColor Cyan
    Remove-PathIfExists -Path $buildDir -Recurse
    Remove-PathIfExists -Path $layerZip
    New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null

    if (Get-Command pip -ErrorAction SilentlyContinue) {
        & pip install -r $requirementsFile -t $pythonDir --quiet
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m pip install -r $requirementsFile -t $pythonDir --quiet
    }
    else {
        throw "pip was not found. Install Python 3.11+ with pip before bootstrapping the layer."
    }

    Assert-LastExitCode "pip install layer dependencies"

    Compress-Archive -Path (Join-Path $buildDir "*") -DestinationPath $layerZip -Force

    Write-Host "Step 3 - Upload layer artifact" -ForegroundColor Cyan
    & aws s3 cp $layerZip "s3://$s3Bucket/$s3Key"
    Assert-LastExitCode "aws s3 cp layer.zip"

    Write-Host "Layer uploaded: s3://$s3Bucket/$s3Key" -ForegroundColor Green
}
finally {
    Remove-PathIfExists -Path $buildDir -Recurse
    Remove-PathIfExists -Path $encryptionConfigFile
    Remove-PathIfExists -Path $publicAccessBlockFile
    Set-Location $repoRoot
}
