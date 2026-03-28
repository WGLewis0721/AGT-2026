param(
    [Parameter(Mandatory = $true)]
    [string]$Client,
    [Parameter(Mandatory = $false)]
    [ValidateSet("dev", "prod")]
    [string]$Environment = "prod"
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
        [string]$Path,
        [switch]$Recurse
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            if ($Recurse) {
                Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            }
            else {
                Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
            }
            return
        }
        catch {
            if (-not (Test-Path -LiteralPath $Path)) {
                return
            }

            if ($attempt -eq 3) {
                throw
            }

            Start-Sleep -Seconds 1
        }
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $backendDir
$lambdaDir = Join-Path $backendDir "lambda"
$buildDir = Join-Path $lambdaDir "build"
$zipPath = Join-Path $lambdaDir "booking-lambda.zip"
$terraformDir = Join-Path $backendDir "terraform"
$varsFile = Join-Path $backendDir "clients/$Client/$Environment.tfvars"
$lambdaSource = Join-Path $lambdaDir "lambda_function.py"
$workspaceName = if ($Environment -eq "prod") { "default" } else { $Environment }

if (-not (Test-Path -LiteralPath $varsFile)) {
    Write-Host "Missing client tfvars file: $varsFile" -ForegroundColor Red
    exit 1
}

Set-Location $backendDir

try {
    Write-Host "━━━ TRA3 Deploy - $Client ($Environment) ━━━" -ForegroundColor Cyan
    Write-Host "Step 1 - Package Lambda" -ForegroundColor Cyan

    Remove-PathIfExists -Path $buildDir -Recurse
    Remove-PathIfExists -Path $zipPath

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
    Remove-PathIfExists -Path $buildDir -Recurse

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

    Write-Host "Step 3 - Terraform workspace" -ForegroundColor Cyan
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

    Write-Host "Step 4 - Terraform apply" -ForegroundColor Cyan
    & terraform apply "-var-file=../clients/$Client/$Environment.tfvars" -auto-approve
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
    Write-Host "5. Re-run .\scripts\deploy.ps1 -Client $Client -Environment $Environment to apply the secret." -ForegroundColor White
}
finally {
    Remove-PathIfExists -Path $buildDir -Recurse
    Set-Location $repoRoot
}
