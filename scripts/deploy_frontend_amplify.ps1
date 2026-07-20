param(
    [string]$Region = "ap-southeast-1",
    [string]$BucketName = "kts-smartagri-frontend-929778605917",
    [string]$AppId = "d3haqw46kdctc4",
    [string]$BranchName = "main"
)

$ErrorActionPreference = "Stop"

function Invoke-AwsText {
    param([string[]]$AwsArgs)

    $output = & aws @AwsArgs
    if ($LASTEXITCODE -ne 0) {
        throw "AWS CLI command failed: aws $($AwsArgs -join ' ')"
    }
    return ($output -join "`n").Trim()
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend-app"
$indexFile = Join-Path $frontendDir "index.html"
$cssDir = Join-Path $frontendDir "css"
$jsDir = Join-Path $frontendDir "js"

foreach ($requiredPath in @($indexFile, $cssDir, $jsDir)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Missing frontend asset: $requiredPath"
    }
}

Invoke-AwsText -AwsArgs @(
    "s3", "cp", $indexFile, "s3://$BucketName/index.html",
    "--region", $Region,
    "--content-type", "text/html; charset=utf-8",
    "--cache-control", "no-cache,no-store,must-revalidate"
) | Out-Null

Invoke-AwsText -AwsArgs @(
    "s3", "sync", $cssDir, "s3://$BucketName/css",
    "--region", $Region,
    "--delete",
    "--cache-control", "public,max-age=300"
) | Out-Null

Invoke-AwsText -AwsArgs @(
    "s3", "sync", $jsDir, "s3://$BucketName/js",
    "--region", $Region,
    "--delete",
    "--exclude", "*.test.js",
    "--cache-control", "public,max-age=300"
) | Out-Null

Invoke-AwsText -AwsArgs @(
    "s3", "rm", "s3://$BucketName/js/app.test.js",
    "--region", $Region,
    "--only-show-errors"
) | Out-Null

$deploymentText = Invoke-AwsText -AwsArgs @(
    "amplify", "start-deployment",
    "--app-id", $AppId,
    "--branch-name", $BranchName,
    "--source-url", "s3://$BucketName/",
    "--source-url-type", "BUCKET_PREFIX",
    "--region", $Region,
    "--output", "json"
)
$deployment = $deploymentText | ConvertFrom-Json
$jobId = $deployment.jobSummary.jobId

for ($attempt = 1; $attempt -le 60; $attempt++) {
    $jobText = Invoke-AwsText -AwsArgs @(
        "amplify", "get-job",
        "--app-id", $AppId,
        "--branch-name", $BranchName,
        "--job-id", $jobId,
        "--region", $Region,
        "--output", "json"
    )
    $status = ($jobText | ConvertFrom-Json).job.summary.status

    if ($status -eq "SUCCEED") {
        Write-Output "Deployment job: $jobId (SUCCEED)"
        Write-Output "Production URL: https://$BranchName.$AppId.amplifyapp.com"
        return
    }
    if ($status -in @("FAILED", "CANCELLED")) {
        throw "Amplify deployment job $jobId ended with status $status."
    }

    Start-Sleep -Seconds 5
}

throw "Timed out waiting for Amplify deployment job $jobId."
