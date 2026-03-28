param(
    [Parameter(Mandatory = $true)]
    [string]$Client
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

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $backendDir
$lambdaDir = Join-Path $backendDir "lambda"
$buildDir = Join-Path $lambdaDir "build"
$zipPath = Join-Path $lambdaDir "booking-lambda.zip"
$terraformDir = Join-Path $backendDir "terraform"
$varsFile = Join-Path $backendDir "clients/$Client/terraform.tfvars"
$lambdaSource = Join-Path $lambdaDir "lambda_function.py"

if (-not (Test-Path -LiteralPath $varsFile)) {
    Write-Host "Missing client tfvars file: $varsFile" -ForegroundColor Red
    exit 1
}

Set-Location $backendDir

try {
    Write-Host "Step 1 - Package Lambda" -ForegroundColor Cyan

    if (Test-Path -LiteralPath $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }

    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }

    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
    Copy-Item -LiteralPath $lambdaSource -Destination $buildDir -Force

    if (Get-Command pip -ErrorAction SilentlyContinue) {
        & pip install stripe requests -t $buildDir --quiet
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m pip install stripe requests -t $buildDir --quiet
    }
    else {
        throw "pip was not found. Install Python 3.11+ with pip before deploying."
    }

    Assert-LastExitCode "pip install stripe requests"

    Compress-Archive -Path (Join-Path $buildDir "*") -DestinationPath $zipPath -Force
    Remove-Item -LiteralPath $buildDir -Recurse -Force

    Write-Host "Lambda package created: $zipPath" -ForegroundColor Green

    Write-Host "Step 2 - Terraform init" -ForegroundColor Cyan
    Set-Location $terraformDir

    if (-not (Test-Path -LiteralPath ".terraform")) {
        & terraform init
        Assert-LastExitCode "terraform init"
        Write-Host "Terraform initialized." -ForegroundColor Green
    }
    else {
        Write-Host "Terraform already initialized." -ForegroundColor Green
    }

    Write-Host "Step 3 - Terraform apply" -ForegroundColor Cyan
    & terraform apply "-var-file=../clients/$Client/terraform.tfvars" -auto-approve
    Assert-LastExitCode "terraform apply"

    Write-Host "Deployment finished successfully." -ForegroundColor Green
    Write-Host "" -ForegroundColor White
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "1. Copy the webhook_url output." -ForegroundColor White
    Write-Host "2. Paste it into Stripe -> Developers -> Webhooks -> Add endpoint." -ForegroundColor White
    Write-Host "3. Set the event to: checkout.session.completed" -ForegroundColor White
    Write-Host "4. Copy the signing secret back into terraform.tfvars as stripe_webhook_secret." -ForegroundColor White
    Write-Host "5. Re-run .\scripts\deploy.ps1 -Client $Client to apply the secret." -ForegroundColor White
}
finally {
    if (Test-Path -LiteralPath $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }

    Set-Location $repoRoot
}
