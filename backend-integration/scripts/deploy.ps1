param(
    [Parameter(Mandatory = $true)]
    [string]$Client,
    [Parameter(Mandatory = $false)]
    [ValidateSet("dev", "prod")]
    [string]$Environment = "prod",
    [Parameter(Mandatory = $false)]
    [switch]$Force
)

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
        [string]$Path
    )

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $backendDir
$lambdaDir = Join-Path $backendDir "lambda"
$zipPath = Join-Path $lambdaDir "lambda_function.zip"
$terraformDir = Join-Path $backendDir "terraform"
$varsFile = Join-Path $backendDir "clients/$Client/$Environment.tfvars"
$lambdaSource = Join-Path $lambdaDir "lambda_function.py"
$workspaceName = if ($Environment -eq "prod") { "default" } else { $Environment }
$backendKey = "terraform-state/$Client/terraform.tfstate"

if (-not (Test-Path -LiteralPath $varsFile)) {
    Write-Host "Missing client tfvars file: $varsFile" -ForegroundColor Red
    exit 1
}

Set-Location $backendDir

try {
    Write-Host "=== TRA3 Deploy: $Client ($Environment) ===" -ForegroundColor Cyan

    Write-Host "Step 0 - Preflight" -ForegroundColor Cyan
    $accountId = ((@(& aws sts get-caller-identity --query Account --output text)) -join "").Trim()
    Assert-LastExitCode "aws sts get-caller-identity"
    $s3Bucket = "tra3-$accountId-deployments"
    $s3FunctionKey = "functions/$Client/$Environment/lambda_function.zip"

    $layerKey = ((@(& aws s3api list-objects-v2 --bucket $s3Bucket --prefix "layers/dependencies/layer.zip" --query "Contents[?Key=='layers/dependencies/layer.zip'].Key" --output text)) -join "").Trim()
    Assert-LastExitCode "aws s3api list-objects-v2"
    if (-not $layerKey) {
        throw "Dependency layer not found in s3://$s3Bucket/layers/dependencies/layer.zip. Run .\\backend-integration\\scripts\\bootstrap-layer.ps1 first."
    }

    Write-Host "Step 1 - Package Lambda" -ForegroundColor Cyan
    Remove-PathIfExists -Path $zipPath
    Compress-Archive -Path $lambdaSource -DestinationPath $zipPath -Force
    Write-Host "Lambda package created: $zipPath" -ForegroundColor Green

    Write-Host "Step 2 - Upload Lambda package" -ForegroundColor Cyan
    & aws s3 cp $zipPath "s3://$s3Bucket/$s3FunctionKey"
    Assert-LastExitCode "aws s3 cp lambda_function.zip"
    Write-Host "Lambda package uploaded: s3://$s3Bucket/$s3FunctionKey" -ForegroundColor Green

    Write-Host "Step 3 - Terraform init" -ForegroundColor Cyan
    Set-Location $terraformDir
    & terraform init -reconfigure "-backend-config=bucket=$s3Bucket" "-backend-config=key=$backendKey" "-backend-config=region=us-east-1" "-backend-config=encrypt=true"
    Assert-LastExitCode "terraform init"
    Write-Host "Terraform initialized." -ForegroundColor Green

    Write-Host "Step 4 - Terraform workspace" -ForegroundColor Cyan
    $workspaceNames = & terraform workspace list
    Assert-LastExitCode "terraform workspace list"
    $workspaceExists = $false
    foreach ($workspace in $workspaceNames) {
        if ($workspace.Replace("*", "").Trim() -eq $workspaceName) {
            $workspaceExists = $true
            break
        }
    }

    if ($workspaceExists) {
        & terraform workspace select $workspaceName
        Assert-LastExitCode "terraform workspace select $workspaceName"
        Write-Host "Terraform workspace selected: $workspaceName" -ForegroundColor Green
    }
    else {
        & terraform workspace new $workspaceName
        Assert-LastExitCode "terraform workspace new $workspaceName"
        Write-Host "Terraform workspace created: $workspaceName" -ForegroundColor Green
    }

    Write-Host "Step 5 - Terraform apply" -ForegroundColor Cyan
    & terraform apply -auto-approve "-var=client_name=$Client" "-var=environment=$Environment" "-var-file=../clients/$Client/$Environment.tfvars"
    Assert-LastExitCode "terraform apply"

    Write-Host "Deployment finished successfully." -ForegroundColor Green
    Write-Host "" -ForegroundColor White
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "1. Copy the webhook_url output for $Environment." -ForegroundColor White
    if ($Environment -eq "dev") {
        Write-Host "2. Paste it into Stripe -> Developers -> Webhooks -> Add endpoint in TEST mode." -ForegroundColor White
    }
    else {
        Write-Host "2. Paste it into Stripe -> Developers -> Webhooks -> Add endpoint in LIVE mode." -ForegroundColor White
    }
    Write-Host "3. Set the event to: checkout.session.completed" -ForegroundColor White
    Write-Host "4. Copy the signing secret back into $Environment.tfvars as stripe_webhook_secret." -ForegroundColor White
    Write-Host "5. Re-run .\\scripts\\deploy.ps1 -Client $Client -Environment $Environment to apply the secret." -ForegroundColor White
}
finally {
    Set-Location $repoRoot
}
