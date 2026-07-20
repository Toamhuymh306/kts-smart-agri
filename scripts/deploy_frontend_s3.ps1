param(
    [string]$Region = "ap-southeast-1",
    [string]$BucketName = "",
    [string]$DistributionComment = "KTs Smart Agriculture frontend"
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

function Invoke-AwsJson {
    param([string[]]$AwsArgs)

    $text = Invoke-AwsText -AwsArgs ($AwsArgs + @("--output", "json"))
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }
    return $text | ConvertFrom-Json
}

function Write-JsonFile {
    param(
        [string]$Path,
        [object]$Value,
        [int]$Depth = 10
    )

    $json = $Value | ConvertTo-Json -Depth $Depth
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

$identity = Invoke-AwsJson -AwsArgs @("sts", "get-caller-identity")
$accountId = $identity.Account
if ([string]::IsNullOrWhiteSpace($BucketName)) {
    $BucketName = "kts-smartagri-frontend-$accountId"
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

$bucketNames = Invoke-AwsJson -AwsArgs @("s3api", "list-buckets", "--query", "Buckets[].Name")
if ($bucketNames -notcontains $BucketName) {
    Invoke-AwsText -AwsArgs @(
        "s3api", "create-bucket",
        "--bucket", $BucketName,
        "--region", $Region,
        "--create-bucket-configuration", "LocationConstraint=$Region"
    ) | Out-Null
}

Invoke-AwsText -AwsArgs @(
    "s3api", "put-public-access-block",
    "--bucket", $BucketName,
    "--public-access-block-configuration",
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
) | Out-Null

Invoke-AwsText -AwsArgs @(
    "s3api", "put-bucket-ownership-controls",
    "--bucket", $BucketName,
    "--ownership-controls", "Rules=[{ObjectOwnership=BucketOwnerEnforced}]"
) | Out-Null

Invoke-AwsText -AwsArgs @(
    "s3api", "put-bucket-encryption",
    "--bucket", $BucketName,
    "--server-side-encryption-configuration",
    "Rules=[{ApplyServerSideEncryptionByDefault={SSEAlgorithm=AES256}}]"
) | Out-Null

Invoke-AwsText -AwsArgs @(
    "s3api", "put-bucket-tagging",
    "--bucket", $BucketName,
    "--tagging", "TagSet=[{Key=Project,Value=KTs-Smart-Agriculture},{Key=Purpose,Value=Frontend-Hosting}]"
) | Out-Null

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

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) "kts-smartagri-cloudfront"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

$oacName = "kts-smartagri-frontend-oac"
$oacList = Invoke-AwsJson -AwsArgs @("cloudfront", "list-origin-access-controls")
$oac = @($oacList.OriginAccessControlList.Items) | Where-Object { $_.Name -eq $oacName } | Select-Object -First 1

if ($null -eq $oac) {
    $oacConfigPath = Join-Path $tempDir "oac-config.json"
    $oacConfig = @{
        Name                          = $oacName
        Description                   = "Private access from CloudFront to the KTs frontend bucket"
        SigningProtocol               = "sigv4"
        SigningBehavior               = "always"
        OriginAccessControlOriginType = "s3"
    }
    Write-JsonFile -Path $oacConfigPath -Value $oacConfig

    $oacResult = Invoke-AwsJson -AwsArgs @(
        "cloudfront", "create-origin-access-control",
        "--origin-access-control-config", "file://$oacConfigPath"
    )
    $oacId = $oacResult.OriginAccessControl.Id
} else {
    $oacId = $oac.Id
}

$distributionList = Invoke-AwsJson -AwsArgs @("cloudfront", "list-distributions")
$distribution = @($distributionList.DistributionList.Items) |
    Where-Object { $_.Comment -eq $DistributionComment } |
    Select-Object -First 1

if ($null -eq $distribution) {
    $originId = "S3-$BucketName"
    $distributionConfigPath = Join-Path $tempDir "distribution-config.json"
    $distributionConfig = @{
        CallerReference  = "kts-smartagri-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
        Comment          = $DistributionComment
        Enabled          = $true
        IsIPV6Enabled    = $true
        HttpVersion      = "http2and3"
        PriceClass       = "PriceClass_100"
        DefaultRootObject = "index.html"
        Origins = @{
            Quantity = 1
            Items    = @(
                @{
                    Id                    = $originId
                    DomainName            = "$BucketName.s3.$Region.amazonaws.com"
                    OriginAccessControlId = $oacId
                    S3OriginConfig        = @{ OriginAccessIdentity = "" }
                }
            )
        }
        DefaultCacheBehavior = @{
            TargetOriginId       = $originId
            ViewerProtocolPolicy = "redirect-to-https"
            Compress             = $true
            CachePolicyId        = "658327ea-f89d-4fab-a63d-7e88639e58f6"
            ResponseHeadersPolicyId = "67f7725c-6f97-4210-82d7-5512b31e9d03"
            AllowedMethods       = @{
                Quantity = 2
                Items = @("GET", "HEAD")
                CachedMethods = @{ Quantity = 2; Items = @("GET", "HEAD") }
            }
        }
        CustomErrorResponses = @{
            Quantity = 2
            Items = @(
                @{ ErrorCode = 403; ResponsePagePath = "/index.html"; ResponseCode = "200"; ErrorCachingMinTTL = 0 },
                @{ ErrorCode = 404; ResponsePagePath = "/index.html"; ResponseCode = "200"; ErrorCachingMinTTL = 0 }
            )
        }
        Restrictions = @{ GeoRestriction = @{ RestrictionType = "none"; Quantity = 0 } }
        ViewerCertificate = @{ CloudFrontDefaultCertificate = $true }
    }
    Write-JsonFile -Path $distributionConfigPath -Value $distributionConfig -Depth 12

    $distributionResult = Invoke-AwsJson -AwsArgs @(
        "cloudfront", "create-distribution",
        "--distribution-config", "file://$distributionConfigPath"
    )
    $distributionId = $distributionResult.Distribution.Id
    $distributionDomain = $distributionResult.Distribution.DomainName
} else {
    $distributionId = $distribution.Id
    $distributionDomain = $distribution.DomainName
}

$bucketPolicyPath = Join-Path $tempDir "bucket-policy.json"
$bucketPolicy = @{
    Version = "2012-10-17"
    Statement = @(
        @{
            Sid       = "AllowCloudFrontServicePrincipalReadOnly"
            Effect    = "Allow"
            Principal = @{ Service = "cloudfront.amazonaws.com" }
            Action    = "s3:GetObject"
            Resource  = "arn:aws:s3:::$BucketName/*"
            Condition = @{
                StringEquals = @{
                    "AWS:SourceArn" = "arn:aws:cloudfront::$accountId`:distribution/$distributionId"
                }
            }
        }
    )
}
Write-JsonFile -Path $bucketPolicyPath -Value $bucketPolicy -Depth 8

Invoke-AwsText -AwsArgs @(
    "s3api", "put-bucket-policy",
    "--bucket", $BucketName,
    "--policy", "file://$bucketPolicyPath"
) | Out-Null

Invoke-AwsText -AwsArgs @(
    "cloudfront", "create-invalidation",
    "--distribution-id", $distributionId,
    "--paths", "/*"
) | Out-Null

Write-Output "Bucket: $BucketName"
Write-Output "Distribution: $distributionId"
Write-Output "Production URL: https://$distributionDomain"
Write-Output "CloudFront deployment can take several minutes to reach the Deployed state."
