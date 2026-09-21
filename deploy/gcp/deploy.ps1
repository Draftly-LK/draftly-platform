[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z][a-z0-9-]{4,28}[a-z0-9]$')]
    [string]$ProjectId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string]$ClerkIssuer,

    [ValidateSet('preview', 'staging', 'production')]
    [string]$Environment = 'preview',

    [string]$Region = 'asia-south1',

    [string]$EvidenceLocation = 'asia-southeast1',

    [switch]$ApproveRealDataStorage
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

function Invoke-Gcloud {
    & $gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed with exit code $LASTEXITCODE." }
}

$billingEnabled = (& $gcloud billing projects describe $ProjectId --format='value(billingEnabled)' 2>$null).Trim()
if ($billingEnabled -ne 'True') { throw "Billing is not enabled for '$ProjectId'. Nothing was deployed." }

$secretKinds = @('database-url', 'database-url-direct', 'clerk-secret-key', 'clerk-publishable-key', 'party-identifier-key', 'party-blind-index-key', 'api-cursor-signing-key')
foreach ($kind in $secretKinds) {
    $secret = "draftly-$kind-$Environment"
    & $gcloud secrets versions describe latest --secret=$secret --project=$ProjectId *> $null
    if ($LASTEXITCODE -ne 0) { throw "Secret '$secret' needs an enabled version before deployment." }
}

$tag = (& git -C $repoRoot rev-parse --short=12 HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not determine the Git revision.' }
$registry = "$Region-docker.pkg.dev/$ProjectId/draftly-$Environment"
$backendImage = "$registry/backend:$tag"
$frontendImage = "$registry/frontend:$tag"
$landingImage = "$registry/landing:$tag"
$evidenceBucket = "$ProjectId-draftly-evidence-$Environment"
$pilotBucket = "$ProjectId-draftly-pilot-$Environment"
$buildBucket = "$ProjectId-draftly-build-$Environment"

Push-Location $repoRoot
try {
    Invoke-Gcloud builds submit backend --tag=$backendImage --gcs-source-staging-dir="gs://$buildBucket/source" --project=$ProjectId
    Invoke-Gcloud builds submit landing-page --tag=$landingImage --gcs-source-staging-dir="gs://$buildBucket/source" --project=$ProjectId
} finally {
    Pop-Location
}

$migrationJob = "draftly-migrate-$Environment"
Invoke-Gcloud run jobs deploy $migrationJob --image=$backendImage --region=$Region --service-account="draftly-api-$Environment@$ProjectId.iam.gserviceaccount.com" --command=uv --args=run,alembic,upgrade,head --set-secrets="DATABASE_URL=draftly-database-url-$Environment`:latest,DATABASE_URL_DIRECT=draftly-database-url-direct-$Environment`:latest" --project=$ProjectId
Invoke-Gcloud run jobs execute $migrationJob --region=$Region --wait --project=$ProjectId

$storageMode = if ($ApproveRealDataStorage) { 'gcs' } else { 'filesystem' }
$storageApproved = if ($ApproveRealDataStorage) { 'true' } else { 'false' }
$apiName = "draftly-api-$Environment"
$apiSecrets = "DATABASE_URL=draftly-database-url-$Environment`:latest,DATABASE_URL_DIRECT=draftly-database-url-direct-$Environment`:latest,CLERK_SECRET_KEY=draftly-clerk-secret-key-$Environment`:latest,PARTY_IDENTIFIER_KEY=draftly-party-identifier-key-$Environment`:latest,PARTY_BLIND_INDEX_KEY=draftly-party-blind-index-key-$Environment`:latest,API_CURSOR_SIGNING_KEY=draftly-api-cursor-signing-key-$Environment`:latest"
$initialApiVars = "ENVIRONMENT=$Environment,GCP_PROJECT_ID=$ProjectId,GCP_LOCATION=$Region,DRAFTLY_GCS_PROJECT_ID=$ProjectId,DRAFTLY_GCS_BUCKET=$evidenceBucket,DRAFTLY_GCS_LOCATION=$EvidenceLocation,DRAFTLY_STORAGE_REAL_DATA_APPROVED=$storageApproved,SOURCE_FILE_STORAGE=$storageMode,CLERK_ISSUER=$ClerkIssuer,CLERK_AUTHORIZED_PARTY=https://pending.invalid,ALLOWED_ORIGINS=https://pending.invalid,EXTRACTION_PROVIDER=gemini,PROVIDER_DATA_APPROVAL=false"
Invoke-Gcloud run deploy $apiName --image=$backendImage --region=$Region --service-account="draftly-api-$Environment@$ProjectId.iam.gserviceaccount.com" --allow-unauthenticated --set-env-vars=$initialApiVars --set-secrets=$apiSecrets --cpu=1 --memory=1Gi --min=0 --max=5 --project=$ProjectId
$apiUrl = (& $gcloud run services describe $apiName --region=$Region --project=$ProjectId --format='value(status.url)').Trim()
if (-not $apiUrl) { throw 'Cloud Run did not return an API URL.' }

$publishableKey = (& $gcloud secrets versions access latest --secret="draftly-clerk-publishable-key-$Environment" --project=$ProjectId).Trim()
if ($LASTEXITCODE -ne 0 -or -not $publishableKey) { throw 'Could not read the Clerk publishable key.' }
Push-Location $repoRoot
try {
    Invoke-Gcloud builds submit . --config=deploy/gcp/cloudbuild.frontend.yaml --gcs-source-staging-dir="gs://$buildBucket/source" --substitutions="_IMAGE=$frontendImage,_API_URL=$apiUrl,_CLERK_PUBLISHABLE_KEY=$publishableKey" --project=$ProjectId
} finally {
    Pop-Location
}

$webName = "draftly-web-$Environment"
Invoke-Gcloud run deploy $webName --image=$frontendImage --region=$Region --service-account="draftly-web-$Environment@$ProjectId.iam.gserviceaccount.com" --allow-unauthenticated --set-env-vars="NEXT_PUBLIC_API_BASE_URL=$apiUrl,NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$publishableKey" --set-secrets="CLERK_SECRET_KEY=draftly-clerk-secret-key-$Environment`:latest" --cpu=1 --memory=512Mi --min=0 --max=5 --project=$ProjectId
$webUrl = (& $gcloud run services describe $webName --region=$Region --project=$ProjectId --format='value(status.url)').Trim()
if (-not $webUrl) { throw 'Cloud Run did not return a frontend URL.' }

$finalApiVars = "ALLOWED_ORIGINS=$webUrl,CLERK_AUTHORIZED_PARTY=$webUrl"
Invoke-Gcloud run services update $apiName --region=$Region --update-env-vars=$finalApiVars --project=$ProjectId

$landingName = "draftly-landing-$Environment"
Invoke-Gcloud run deploy $landingName --image=$landingImage --region=$Region --service-account="draftly-landing-$Environment@$ProjectId.iam.gserviceaccount.com" --allow-unauthenticated --set-env-vars="DRAFTLY_APP_URL=$webUrl,PILOT_GCS_BUCKET=$pilotBucket" --cpu=1 --memory=256Mi --min=0 --max=3 --project=$ProjectId
$landingUrl = (& $gcloud run services describe $landingName --region=$Region --project=$ProjectId --format='value(status.url)').Trim()

$workerVars = "ENVIRONMENT=$Environment,GCP_PROJECT_ID=$ProjectId,GCP_LOCATION=$Region,DRAFTLY_GCS_PROJECT_ID=$ProjectId,DRAFTLY_GCS_BUCKET=$evidenceBucket,DRAFTLY_GCS_LOCATION=$EvidenceLocation,DRAFTLY_STORAGE_REAL_DATA_APPROVED=$storageApproved,SOURCE_FILE_STORAGE=$storageMode,CLERK_ISSUER=$ClerkIssuer,CLERK_AUTHORIZED_PARTY=$webUrl,ALLOWED_ORIGINS=$webUrl,EXTRACTION_PROVIDER=gemini,PROVIDER_DATA_APPROVAL=false"
Invoke-Gcloud beta run worker-pools deploy "draftly-worker-$Environment" --image=$backendImage --region=$Region --instances=1 --service-account="draftly-worker-$Environment@$ProjectId.iam.gserviceaccount.com" --command=uv --args=run,python,-m,src.workers.runner --set-env-vars=$workerVars --set-secrets=$apiSecrets --cpu=1 --memory=1Gi --project=$ProjectId

Write-Host "Deployment complete."
Write-Host "Landing:  $landingUrl"
Write-Host "Frontend: $webUrl"
Write-Host "API:      $apiUrl"
if (-not $ApproveRealDataStorage) {
    Write-Warning 'Evidence uploads remain disabled. Rerun with -ApproveRealDataStorage only after the storage approval in backend/docs/services/storage-service.md is recorded.'
}
