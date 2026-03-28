# bootstrap-layer.ps1
# Builds the TRA3 Lambda dependency layer and uploads to S3
# Run from repo root: .\backend-integration\scripts\bootstrap-layer.ps1
# Prerequisites: Python 3.11+, pip, AWS CLI configured

param()

$ErrorActionPreference = "Stop"
$StartTime = Get-Date

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  TRA3 Layer Bootstrap" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Get AWS account ID
Write-Host "[STEP 1/5] Getting AWS account ID..." -ForegroundColor Cyan
Write-Host "  > aws sts get-caller-identity --query Account --output text" -ForegroundColor DarkGray
$AccountId = aws sts get-caller-identity --query Account --output text
Write-Host "  Account ID: $AccountId" -ForegroundColor Green
$S3Bucket = "tra3-$AccountId-deployments"
Write-Host "  S3 Bucket:  $S3Bucket" -ForegroundColor Green
Write-Host ""

# Create build directory
Write-Host "[STEP 2/5] Creating build directory..." -ForegroundColor Cyan
$BuildDir = "backend-integration\layer-build"
if (Test-Path $BuildDir) {
    Write-Host "  > Remove-Item -Recurse -Force $BuildDir" -ForegroundColor DarkGray
    Remove-Item -Recurse -Force $BuildDir
}
Write-Host "  > New-Item -ItemType Directory -Path $BuildDir\python" -ForegroundColor DarkGray
New-Item -ItemType Directory -Path "$BuildDir\python" | Out-Null
Write-Host "  ✓ Build directory created" -ForegroundColor Green
Write-Host ""

# Install dependencies
Write-Host "[STEP 3/5] Installing Python dependencies..." -ForegroundColor Cyan
Write-Host "  > pip install -r backend-integration\layer\requirements.txt -t $BuildDir\python" -ForegroundColor DarkGray
pip install -r backend-integration\layer\requirements.txt -t $BuildDir\python
Write-Host "  ✓ Dependencies installed" -ForegroundColor Green
Write-Host ""

# Create layer zip
Write-Host "[STEP 4/5] Creating layer zip..." -ForegroundColor Cyan
$LayerZip = "backend-integration\layer.zip"
if (Test-Path $LayerZip) { Remove-Item -Force $LayerZip }
Write-Host "  > Compress-Archive -Path $BuildDir\* -DestinationPath $LayerZip" -ForegroundColor DarkGray
Compress-Archive -Path "$BuildDir\*" -DestinationPath $LayerZip
$SizeKB = [math]::Round((Get-Item $LayerZip).Length / 1KB, 1)
Write-Host "  ✓ Layer zip created ($SizeKB KB)" -ForegroundColor Green
Write-Host ""

# Upload to S3
Write-Host "[STEP 5/5] Uploading to S3..." -ForegroundColor Cyan
$S3Key = "layers/dependencies/layer.zip"
Write-Host "  > aws s3 cp $LayerZip s3://$S3Bucket/$S3Key" -ForegroundColor DarkGray
aws s3 cp $LayerZip "s3://$S3Bucket/$S3Key"
Write-Host "  ✓ Layer uploaded to S3" -ForegroundColor Green
Write-Host ""

# Cleanup
Write-Host "  > Remove-Item -Recurse -Force $BuildDir" -ForegroundColor DarkGray
Remove-Item -Recurse -Force $BuildDir
Write-Host "  > Remove-Item -Force $LayerZip" -ForegroundColor DarkGray
Remove-Item -Force $LayerZip

$Elapsed = [math]::Round(((Get-Date) - $StartTime).TotalSeconds, 1)
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "  ✅ Bootstrap complete ($Elapsed seconds)" -ForegroundColor Green
Write-Host "  S3: s3://$S3Bucket/$S3Key" -ForegroundColor White
Write-Host "  Run deploy.ps1 to deploy infrastructure." -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
