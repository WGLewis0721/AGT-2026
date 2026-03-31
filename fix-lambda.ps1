<#
.SYNOPSIS
    Fixes merge conflict artifacts in lambda_function.py
    Run from: C:\Users\Willi\OneDrive\Documents\agt-website
#>

$ErrorActionPreference = "Stop"
$FilePath = "backend-integration\lambda\lambda_function.py"

Write-Host "Reading lambda_function.py..." -ForegroundColor Cyan
$lines = Get-Content $FilePath

# Step 1: Remove all git conflict markers
Write-Host "Removing conflict markers..." -ForegroundColor Cyan
$lines = $lines | Where-Object {
    $_ -notmatch "^<<<<<<< " -and
    $_ -notmatch "^=======$" -and
    $_ -notmatch "^>>>>>>> "
}

# Step 2: Fix empty _parse_calcom_service_address function
Write-Host "Fixing _parse_calcom_service_address..." -ForegroundColor Cyan
$output = [System.Collections.Generic.List[string]]::new()
$i = 0
while ($i -lt $lines.Count) {
    $line = $lines[$i]
    $output.Add($line)

    if ($line -match "^def _parse_calcom_service_address\(") {
        $j = $i + 1
        while ($j -lt $lines.Count -and $lines[$j].Trim() -eq "") { $j++ }
        if ($j -lt $lines.Count -and $lines[$j] -match "^def ") {
            $output.Add('    """Extract address of service from Cal.com booking responses."""')
            $output.Add('    address = _calcom_response_value(')
            $output.Add('        responses,')
            $output.Add('        "address-of-service", "addressOfService",')
            $output.Add('        "address_of_service", "address",')
            $output.Add('        "Address of Service", "location"')
            $output.Add('    )')
            $output.Add('    if address and not str(address).strip():')
            $output.Add('        address = None')
            $output.Add('    return address')
            Write-Host "  Inserted body for _parse_calcom_service_address" -ForegroundColor Green
        }
    }
    $i++
}

# Step 3: Write fixed file
Write-Host "Writing fixed file..." -ForegroundColor Cyan
$output | Set-Content $FilePath -Encoding UTF8

# Step 4: Syntax check
Write-Host "Running syntax check..." -ForegroundColor Cyan
$result = python -m py_compile $FilePath 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Syntax OK" -ForegroundColor Green
} else {
    Write-Host "❌ Syntax error:" -ForegroundColor Red
    Write-Host $result -ForegroundColor Red
    exit 1
}

# Step 5: Check for remaining conflict markers
$remaining = Select-String -Path $FilePath -Pattern "<<<<<<|=======|>>>>>>>" -SimpleMatch
if ($remaining) {
    Write-Host "WARNING: Conflict markers still present:" -ForegroundColor Yellow
    $remaining | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "✅ No conflict markers remaining" -ForegroundColor Green
}

Write-Host ""
Write-Host "Ready to deploy." -ForegroundColor Green