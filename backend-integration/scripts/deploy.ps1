# deploy.ps1
# Deploys TRA3 infrastructure for a specific client and environment
# Run from repo root:
#   .\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch
#   .\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment dev
#   .\backend-integration\scripts\deploy.ps1 -Client gentlemens-touch -Environment prod -Force

param(
    [Parameter(Mandatory=$true)]
    [string]$Client,

    [Parameter(Mandatory=$false)]
    [ValidateSet("dev","prod")]
    [string]$Environment = "prod",

    [Parameter(Mandatory=$false)]
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$StartTime = Get-Date
$TfVarsFile = "backend-integration\clients\$Client\$Environment.tfvars"
$TerraformDir = "backend-integration\terraform"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  TRA3 Deploy" -ForegroundColor Cyan
Write-Host "  Client:      $Client" -ForegroundColor White
Write-Host "  Environment: $Environment" -ForegroundColor White
Write-Host "  Time:        $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# ─── STEP 0: PREFLIGHT ───────────────────────────────────────
Write-Host "━━━ [STEP 0/5] Preflight Checks ━━━" -ForegroundColor Cyan

Write-Host "  > terraform --version" -ForegroundColor DarkGray
terraform --version

Write-Host "  > aws --version" -ForegroundColor DarkGray
aws --version

Write-Host "  > aws sts get-caller-identity" -ForegroundColor DarkGray
$Identity = aws sts get-caller-identity | ConvertFrom-Json
Write-Host "  Account: $($Identity.Account)" -ForegroundColor Green
Write-Host "  ARN:     $($Identity.Arn)" -ForegroundColor Green
$AccountId = $Identity.Account
$S3Bucket = "tra3-$AccountId-deployments"

if (-not (Test-Path $TfVarsFile)) {
    Write-Host "  ❌ tfvars not found: $TfVarsFile" -ForegroundColor Red
    Write-Host "     Create this file before deploying." -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✓ tfvars found: $TfVarsFile" -ForegroundColor Green

Write-Host "  > aws s3 ls s3://$S3Bucket/layers/dependencies/layer.zip" -ForegroundColor DarkGray
$LayerCheck = aws s3 ls "s3://$S3Bucket/layers/dependencies/layer.zip" 2>&1
if (-not $LayerCheck) {
    Write-Host "  ❌ Layer not found in S3" -ForegroundColor Red
    Write-Host "     Run: .\backend-integration\scripts\bootstrap-layer.ps1" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✓ Layer found in S3" -ForegroundColor Green
Write-Host "  ✓ All preflight checks passed" -ForegroundColor Green
Write-Host ""

# ─── STEP 1: PACKAGE LAMBDA ──────────────────────────────────
$StepStart = Get-Date
Write-Host "━━━ [STEP 1/5] Packaging Lambda ━━━" -ForegroundColor Cyan

$LambdaZip = "backend-integration\lambda\lambda_function.zip"
if (Test-Path $LambdaZip) {
    Write-Host "  > Remove-Item $LambdaZip" -ForegroundColor DarkGray
    Remove-Item -Force $LambdaZip
}

Write-Host "  > Compress-Archive lambda_function.py → lambda_function.zip" -ForegroundColor DarkGray
Compress-Archive -Path "backend-integration\lambda\lambda_function.py" -DestinationPath $LambdaZip
$SizeKB = [math]::Round((Get-Item $LambdaZip).Length / 1KB, 1)
Write-Host "  ✓ Zipped ($SizeKB KB)" -ForegroundColor Green

$S3FunctionKey = "functions/$Client/$Environment/lambda_function.zip"
Write-Host "  > aws s3 cp $LambdaZip s3://$S3Bucket/$S3FunctionKey" -ForegroundColor DarkGray
aws s3 cp $LambdaZip "s3://$S3Bucket/$S3FunctionKey"
$StepElapsed = [math]::Round(((Get-Date) - $StepStart).TotalSeconds, 1)
Write-Host "  ✓ Lambda uploaded to S3 ($StepElapsed seconds)" -ForegroundColor Green
Write-Host ""

# ─── STEP 2: TERRAFORM INIT ──────────────────────────────────
$StepStart = Get-Date
Write-Host "━━━ [STEP 2/5] Terraform Init ━━━" -ForegroundColor Cyan

Set-Location $TerraformDir

# Workspace management
if ($Environment -eq "dev") {
    Write-Host "  > terraform workspace select dev (or new)" -ForegroundColor DarkGray
    $WorkspaceList = terraform workspace list 2>&1
    if ($WorkspaceList -match "dev") {
        terraform workspace select dev
    } else {
        terraform workspace new dev
    }
} else {
    Write-Host "  > terraform workspace select default" -ForegroundColor DarkGray
    terraform workspace select default
}
Write-Host "  ✓ Workspace: $Environment" -ForegroundColor Green

$NeedsInit = $Force -or (-not (Test-Path ".terraform"))
if ($NeedsInit) {
    $InitCmd = "terraform init " +
        "-backend-config=`"bucket=$S3Bucket`" " +
        "-backend-config=`"key=terraform-state/$Client/$Environment/terraform.tfstate`" " +
        "-backend-config=`"region=us-east-1`""
    Write-Host "  > $InitCmd" -ForegroundColor DarkGray
    Invoke-Expression $InitCmd
} else {
    Write-Host "  ↷ Skipping init (.terraform exists — use -Force to reinitialize)" -ForegroundColor DarkGray
}
$StepElapsed = [math]::Round(((Get-Date) - $StepStart).TotalSeconds, 1)
Write-Host "  ✓ Terraform initialized ($StepElapsed seconds)" -ForegroundColor Green
Write-Host ""

# ─── STEP 3: TERRAFORM APPLY ─────────────────────────────────
$StepStart = Get-Date
Write-Host "━━━ [STEP 3/5] Terraform Apply ━━━" -ForegroundColor Cyan

$ApplyCmd = "terraform apply -auto-approve " +
    "-var=`"client_name=$Client`" " +
    "-var=`"environment=$Environment`" " +
    "-var-file=`"..\clients\$Client\$Environment.tfvars`""
Write-Host "  > $ApplyCmd" -ForegroundColor DarkGray
Invoke-Expression $ApplyCmd

$StepElapsed = [math]::Round(((Get-Date) - $StepStart).TotalSeconds, 1)
Write-Host "  ✓ Infrastructure applied ($StepElapsed seconds)" -ForegroundColor Green
Write-Host ""

# ─── STEP 4: OUTPUTS ─────────────────────────────────────────
Write-Host "━━━ [STEP 4/5] Outputs ━━━" -ForegroundColor Cyan
Write-Host "  > terraform output" -ForegroundColor DarkGray
$Outputs = terraform output -json | ConvertFrom-Json
$WebhookUrl = $Outputs.webhook_url.value
Write-Host ""
Write-Host "  📋 WEBHOOK URL:" -ForegroundColor Cyan
Write-Host "  $WebhookUrl" -ForegroundColor White
Write-Host ""

Set-Location ..\..\..

# ─── STEP 5: NEXT STEPS ──────────────────────────────────────
$TotalElapsed = [math]::Round(((Get-Date) - $StartTime).TotalSeconds, 1)
Write-Host "━━━ [STEP 5/5] Deploy Complete ━━━" -ForegroundColor Green
Write-Host ""
Write-Host "  Total time: $TotalElapsed seconds" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Copy the webhook URL above" -ForegroundColor White

if ($Environment -eq "dev") {
    Write-Host "  2. Stripe Dashboard → toggle to TEST mode" -ForegroundColor White
} else {
    Write-Host "  2. Stripe Dashboard → toggle to LIVE mode" -ForegroundColor White
}

Write-Host "  3. Developers → Webhooks → Add endpoint" -ForegroundColor White
Write-Host "  4. Event: checkout.session.completed" -ForegroundColor White
Write-Host "  5. Copy the signing secret from Stripe" -ForegroundColor White
Write-Host "  6. Update clients\$Client\$Environment.tfvars → stripe_webhook_secret" -ForegroundColor White
Write-Host "  7. Re-run this script to push the updated secret" -ForegroundColor White
Write-Host "     (No infrastructure changes — Lambda env vars only)" -ForegroundColor DarkGray
Write-Host ""
