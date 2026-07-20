param(
    [Parameter(Mandatory = $true)]
    [string]$AwsRegion,

    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [Parameter(Mandatory = $true)]
    [string]$EcrRepository,

    [Parameter(Mandatory = $true)]
    [string]$LambdaFunctionName,

    [Parameter(Mandatory = $true)]
    [string]$ProcessedBucket,

    [Parameter(Mandatory = $true)]
    [string]$ResultTable,

    [ValidateSet("lenet", "resnet")]
    [string]$ModelName = "resnet"
)

$imageTag = "latest"
$ecrUri = "$AccountId.dkr.ecr.$AwsRegion.amazonaws.com/$EcrRepository`:$imageTag"

Write-Host "1) Login to ECR"
aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$AwsRegion.amazonaws.com"
if (-not $?) { throw "ECR login failed" }

Write-Host "2) Build Lambda inference container image"
docker build -t "$EcrRepository`:$imageTag" -f "aws/lambda_inference/Dockerfile" .
if (-not $?) { throw "Docker build failed" }

Write-Host "3) Smoke test packaged model"
docker run --rm --entrypoint python -e "MODEL_NAME=$ModelName" "$EcrRepository`:$imageTag" `
  -c "from runtime import load_assets; assets=load_assets(); print(assets.model_name, len(assets.class_names))"
if (-not $?) { throw "Docker model smoke test failed" }

Write-Host "4) Tag and push image"
docker tag "$EcrRepository`:$imageTag" $ecrUri
docker push $ecrUri
if (-not $?) { throw "Docker push failed" }

Write-Host "5) Update Lambda function image"
aws lambda update-function-code `
  --function-name $LambdaFunctionName `
  --image-uri $ecrUri `
  --region $AwsRegion
if (-not $?) { throw "Lambda function code update failed" }

Write-Host "6) Update Lambda environment variables"
aws lambda update-function-configuration `
  --function-name $LambdaFunctionName `
  --region $AwsRegion `
  --environment "Variables={MODEL_NAME=$ModelName,PROCESSED_BUCKET=$ProcessedBucket,RESULT_TABLE=$ResultTable}"
if (-not $?) { throw "Lambda configuration update failed" }

Write-Host "Deployment completed."
