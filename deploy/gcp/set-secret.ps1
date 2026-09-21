[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [Parameter(Mandatory = $true)]
    [ValidateSet('database-url', 'database-url-direct', 'clerk-secret-key', 'clerk-publishable-key', 'party-identifier-key', 'party-blind-index-key', 'api-cursor-signing-key')]
    [string]$Kind,

    [ValidateSet('preview', 'staging', 'production')]
    [string]$Environment = 'preview'
)

$ErrorActionPreference = 'Stop'
$gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source
$secret = "draftly-$Kind-$Environment"
$secure = Read-Host "Enter the value for $secret" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $plain | & $gcloud secrets versions add $secret --data-file=- --project=$ProjectId
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed with exit code $LASTEXITCODE." }
} finally {
    if ($null -ne $plain) { $plain = $null }
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}

Write-Host "Added a new version to $secret."
