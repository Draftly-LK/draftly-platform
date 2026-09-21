[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z][a-z0-9-]{4,28}[a-z0-9]$')]
    [string]$ProjectId,

    [ValidateSet('preview', 'staging', 'production')]
    [string]$Environment = 'preview',

    [string]$Region = 'asia-south1',

    [string]$EvidenceLocation = 'asia-southeast1'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source

function Invoke-Gcloud {
    & $gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed with exit code $LASTEXITCODE." }
}

function Test-GcloudResource([scriptblock]$Command) {
    & $Command *> $null
    return $LASTEXITCODE -eq 0
}

$billingEnabled = (& $gcloud billing projects describe $ProjectId --format='value(billingEnabled)' 2>$null).Trim()
if ($billingEnabled -ne 'True') {
    throw "Billing is not enabled for '$ProjectId'. Link an active billing account, then rerun this script. No resources were changed."
}

Invoke-Gcloud config set project $ProjectId
Invoke-Gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com iam.googleapis.com iamcredentials.googleapis.com

$repository = "draftly-$Environment"
if (-not (Test-GcloudResource { & $gcloud artifacts repositories describe $repository --location $Region --project $ProjectId })) {
    Invoke-Gcloud artifacts repositories create $repository --repository-format=docker --location=$Region --description="Draftly $Environment container images" --project=$ProjectId
}

$serviceAccounts = @('landing', 'web', 'api', 'worker')
foreach ($name in $serviceAccounts) {
    $accountId = "draftly-$name-$Environment"
    $email = "$accountId@$ProjectId.iam.gserviceaccount.com"
    if (-not (Test-GcloudResource { & $gcloud iam service-accounts describe $email --project $ProjectId })) {
        Invoke-Gcloud iam service-accounts create $accountId --display-name="Draftly $Environment $name" --project=$ProjectId
    }
}

$evidenceBucket = "$ProjectId-draftly-evidence-$Environment"
$pilotBucket = "$ProjectId-draftly-pilot-$Environment"
$buildBucket = "$ProjectId-draftly-build-$Environment"
foreach ($bucket in @($evidenceBucket, $pilotBucket, $buildBucket)) {
    if (-not (Test-GcloudResource { & $gcloud storage buckets describe "gs://$bucket" --project $ProjectId })) {
        $location = if ($bucket -eq $evidenceBucket) { $EvidenceLocation } else { $Region }
        Invoke-Gcloud storage buckets create "gs://$bucket" --project=$ProjectId --location=$location --uniform-bucket-level-access --public-access-prevention
    }
    $updateArgs = @('storage', 'buckets', 'update', "gs://$bucket", '--public-access-prevention', '--uniform-bucket-level-access')
    if ($bucket -ne $buildBucket) { $updateArgs += '--versioning' }
    Invoke-Gcloud @updateArgs
}

$apiMember = "serviceAccount:draftly-api-$Environment@$ProjectId.iam.gserviceaccount.com"
$workerMember = "serviceAccount:draftly-worker-$Environment@$ProjectId.iam.gserviceaccount.com"
$landingMember = "serviceAccount:draftly-landing-$Environment@$ProjectId.iam.gserviceaccount.com"
foreach ($member in @($apiMember, $workerMember)) {
    Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$evidenceBucket" --member=$member --role=roles/storage.objectAdmin
    Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$evidenceBucket" --member=$member --role=roles/storage.legacyBucketReader
}
Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$pilotBucket" --member=$landingMember --role=roles/storage.objectCreator

$secretKinds = @(
    'database-url',
    'database-url-direct',
    'clerk-secret-key',
    'clerk-publishable-key',
    'party-identifier-key',
    'party-blind-index-key',
    'api-cursor-signing-key'
)
foreach ($kind in $secretKinds) {
    $secret = "draftly-$kind-$Environment"
    if (-not (Test-GcloudResource { & $gcloud secrets describe $secret --project $ProjectId })) {
        Invoke-Gcloud secrets create $secret --replication-policy=automatic --project=$ProjectId
    }
}

$runtimeSecretAccess = @{
    "draftly-api-$Environment@$ProjectId.iam.gserviceaccount.com" = @('database-url', 'database-url-direct', 'clerk-secret-key', 'party-identifier-key', 'party-blind-index-key', 'api-cursor-signing-key')
    "draftly-worker-$Environment@$ProjectId.iam.gserviceaccount.com" = @('database-url', 'database-url-direct', 'clerk-secret-key', 'party-identifier-key', 'party-blind-index-key', 'api-cursor-signing-key')
    "draftly-web-$Environment@$ProjectId.iam.gserviceaccount.com" = @('clerk-secret-key')
}
foreach ($entry in $runtimeSecretAccess.GetEnumerator()) {
    foreach ($kind in $entry.Value) {
        Invoke-Gcloud secrets add-iam-policy-binding "draftly-$kind-$Environment" --member="serviceAccount:$($entry.Key)" --role=roles/secretmanager.secretAccessor --project=$ProjectId
    }
}

$buildAccount = (& $gcloud builds get-default-service-account --project $ProjectId).Trim()
if ($LASTEXITCODE -ne 0 -or -not $buildAccount) { throw 'Could not resolve the Cloud Build service account.' }
foreach ($role in @('roles/artifactregistry.writer', 'roles/logging.logWriter')) {
    Invoke-Gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$buildAccount" --role=$role --condition=None
}
Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$buildBucket" --member="serviceAccount:$buildAccount" --role=roles/storage.objectViewer
Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$buildBucket" --member="serviceAccount:$buildAccount" --role=roles/storage.legacyBucketReader

Write-Host "GCP foundation is ready."
Write-Host "Evidence bucket: gs://$evidenceBucket"
Write-Host "Pilot bucket:    gs://$pilotBucket"
Write-Host "Build bucket:    gs://$buildBucket"
Write-Host "Next: add an enabled version to every draftly-*-$Environment secret, then run deploy.ps1."
