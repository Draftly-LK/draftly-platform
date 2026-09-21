[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[^@\s]+@[^@\s]+\.[^@\s]+$')]
    [string]$Email,

    [ValidateSet('preview', 'staging', 'production')]
    [string]$Environment = 'preview'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source
$member = "user:$Email"

function Invoke-Gcloud {
    & $gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed with exit code $LASTEXITCODE." }
}

# Deployment and diagnosis without project Owner, IAM admin, or access to client evidence.
foreach ($role in @('roles/run.admin', 'roles/artifactregistry.writer', 'roles/cloudbuild.builds.editor', 'roles/logging.viewer', 'roles/secretmanager.viewer', 'roles/serviceusage.serviceUsageConsumer')) {
    Invoke-Gcloud projects add-iam-policy-binding $ProjectId --member=$member --role=$role --condition=None
}

$buildBucket = "$ProjectId-draftly-build-$Environment"
Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$buildBucket" --member=$member --role=roles/storage.objectAdmin
Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$buildBucket" --member=$member --role=roles/storage.legacyBucketReader

foreach ($name in @('landing', 'web', 'api', 'worker')) {
    $serviceAccount = "draftly-$name-$Environment@$ProjectId.iam.gserviceaccount.com"
    Invoke-Gcloud iam service-accounts add-iam-policy-binding $serviceAccount --member=$member --role=roles/iam.serviceAccountUser --project=$ProjectId
}

# The publishable Clerk key is needed as a frontend build argument. No other
# secret values are exposed to the teammate by this role set.
Invoke-Gcloud secrets add-iam-policy-binding "draftly-clerk-publishable-key-$Environment" --member=$member --role=roles/secretmanager.secretAccessor --project=$ProjectId

Write-Host "$Email can deploy and inspect Draftly $Environment without project-owner or evidence-bucket access."
