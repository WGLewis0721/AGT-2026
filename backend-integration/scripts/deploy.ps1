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
        Remove-Item -LiteralPath $Path -Force -Recurse
    }
}

function New-ZipFromFiles {
    param(
        [string]$DestinationPath,
        [string[]]$Files
    )

    $stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $stageRoot | Out-Null

    try {
        foreach ($file in $Files) {
            $destination = Join-Path $stageRoot (Split-Path -Leaf $file)
            Copy-Item -LiteralPath $file -Destination $destination -Force
        }

        Remove-PathIfExists -Path $DestinationPath
        Compress-Archive -Path (Join-Path $stageRoot '*') -DestinationPath $DestinationPath -Force
    }
    finally {
        Remove-PathIfExists -Path $stageRoot
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $backendDir
$lambdaDir = Join-Path $backendDir "lambda"
$sharedDir = Join-Path $backendDir "shared"
$apiDir = Join-Path $repoRoot "api"
$costReporterDir = Join-Path $backendDir "cost-reporter"
$webhookZipPath = Join-Path $lambdaDir "lambda_function.zip"
$bookingIntentZipPath = Join-Path $apiDir "booking_intent.zip"
$checkoutZipPath = Join-Path $apiDir "create_checkout_session.zip"
$costReporterZipPath = Join-Path $costReporterDir "cost_reporter.zip"
$terraformDir = Join-Path $backendDir "terraform"
$varsFile = Join-Path $backendDir "clients/$Client/$Environment.tfvars"
$workspaceName = if ($Environment -eq "prod") { "default" } else { $Environment }
$backendKey = "terraform-state/$Client/terraform.tfstate"

$webhookSource = Join-Path $lambdaDir "lambda_function.py"
$bookingIntentSource = Join-Path $apiDir "booking_intent.py"
$checkoutSource = Join-Path $apiDir "create_checkout_session.py"
$sharedSource = Join-Path $sharedDir "booking_common.py"
$costReporterSource = Join-Path $costReporterDir "cost_reporter_handler.py"

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

    $layerKey = ((@(& aws s3api list-objects-v2 --bucket $s3Bucket --prefix "layers/dependencies/layer.zip" --query "Contents[?Key=='layers/dependencies/layer.zip'].Key" --output text)) -join "").Trim()
    Assert-LastExitCode "aws s3api list-objects-v2"
    if (-not $layerKey) {
        throw "Dependency layer not found in s3://$s3Bucket/layers/dependencies/layer.zip. Run .\\backend-integration\\scripts\\bootstrap-layer.ps1 first."
    }

    Write-Host "Step 1 - Package Lambda artifacts" -ForegroundColor Cyan
    New-ZipFromFiles -DestinationPath $webhookZipPath -Files @(
        $webhookSource,
        $sharedSource
    )
    New-ZipFromFiles -DestinationPath $bookingIntentZipPath -Files @(
        $bookingIntentSource,
        $sharedSource
    )
    New-ZipFromFiles -DestinationPath $checkoutZipPath -Files @(
        $checkoutSource,
        $sharedSource
    )
    New-ZipFromFiles -DestinationPath $costReporterZipPath -Files @(
        $costReporterSource
    )
    Write-Host "Webhook package created: $webhookZipPath" -ForegroundColor Green
    Write-Host "Booking intent package created: $bookingIntentZipPath" -ForegroundColor Green
    Write-Host "Checkout session package created: $checkoutZipPath" -ForegroundColor Green
    Write-Host "Cost reporter package created: $costReporterZipPath" -ForegroundColor Green

    Write-Host "Step 2 - Upload Lambda packages" -ForegroundColor Cyan
    $artifacts = @(
        @{
            Label = "Webhook Lambda"
            ZipPath = $webhookZipPath
            S3Key = "functions/$Client/$Environment/lambda_function.zip"
        },
        @{
            Label = "Booking intent Lambda"
            ZipPath = $bookingIntentZipPath
            S3Key = "functions/$Client/$Environment/booking_intent.zip"
        },
        @{
            Label = "Checkout session Lambda"
            ZipPath = $checkoutZipPath
            S3Key = "functions/$Client/$Environment/create_checkout_session.zip"
        },
        @{
            Label = "Cost reporter Lambda"
            ZipPath = $costReporterZipPath
            S3Key = "functions/$Client/$Environment/cost_reporter.zip"
        }
    )

    foreach ($artifact in $artifacts) {
        $localHash = (Get-FileHash -Path $artifact.ZipPath -Algorithm MD5).Hash.ToLower()
        $remoteETag = ((@(& aws s3api list-objects-v2 --bucket $s3Bucket --prefix $artifact.S3Key --query "Contents[?Key=='$($artifact.S3Key)'].ETag | [0]" --output text 2>$null)) -join "").Trim().Trim('"').ToLower()
        Assert-LastExitCode "aws s3api list-objects-v2 $($artifact.S3Key)"
        if ($remoteETag -eq "none") {
            $remoteETag = ""
        }

        if ($localHash -eq $remoteETag) {
            Write-Host "$($artifact.Label) zip unchanged - skipping S3 upload" -ForegroundColor DarkGray
            continue
        }

        Write-Host "$($artifact.Label) zip changed - uploading to S3..." -ForegroundColor DarkGray
        & aws s3 cp $artifact.ZipPath "s3://$s3Bucket/$($artifact.S3Key)"
        Assert-LastExitCode "aws s3 cp $($artifact.S3Key)"
        Write-Host "$($artifact.Label) package uploaded: s3://$s3Bucket/$($artifact.S3Key)" -ForegroundColor Green
    }

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

    $bookingIntentUrl = ((@(& terraform output -raw booking_intent_url)) -join "").Trim()
    Assert-LastExitCode "terraform output booking_intent_url"
    $checkoutUrl = ((@(& terraform output -raw create_checkout_session_url)) -join "").Trim()
    Assert-LastExitCode "terraform output create_checkout_session_url"
    $webhookUrl = ((@(& terraform output -raw webhook_url)) -join "").Trim()
    Assert-LastExitCode "terraform output webhook_url"

    Write-Host "Deployment finished successfully." -ForegroundColor Green
    Write-Host "" -ForegroundColor White
    Write-Host "Endpoints:" -ForegroundColor White
    Write-Host "  booking-intent:          $bookingIntentUrl" -ForegroundColor White
    Write-Host "  create-checkout-session: $checkoutUrl" -ForegroundColor White
    Write-Host "  webhook:                 $webhookUrl" -ForegroundColor White
}
finally {
    Set-Location $repoRoot
}
