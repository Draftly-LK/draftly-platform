# Draftly on Google Cloud

This deployment runs the landing page, Next.js application, FastAPI API, and
background worker on Cloud Run. Google Cloud Storage is private durable storage;
it is not used as the web server because the frontend and API need server-side
runtime behavior.

## Resources

| Component | GCP resource | Public |
| --- | --- | --- |
| Landing page and pilot form | Cloud Run service | Yes |
| Next.js application | Cloud Run service | Yes |
| FastAPI API | Cloud Run service | Yes; application auth still applies |
| Outbox worker | Cloud Run worker pool | No endpoint |
| Database migrations | Cloud Run job | No |
| Source evidence | Private GCS bucket | No |
| Pilot requests | Separate private GCS bucket | No |
| Cloud Build source archives | Separate private GCS bucket | No |
| Credentials and encryption material | Secret Manager | No |
| Images | Artifact Registry | No |

Every runtime has a separate service account. Both buckets enforce uniform
bucket-level access and public-access prevention. The scripts do not create or
download service-account keys.

## Prerequisites

1. Link billing to the project. The current project can be checked with:

   ```powershell
   gcloud billing projects describe himath-unique-project-2026
   ```

2. Create a Neon database and retain both connection strings:
   - pooled URL for `database-url`;
   - direct URL for `database-url-direct` and migrations.
3. Create/configure the Clerk application and retain its issuer, publishable
   key, and secret key.
4. Authenticate the Google Cloud CLI with an account allowed to create IAM,
   Cloud Run, Storage, Secret Manager, Cloud Build, and Artifact Registry
   resources.

The scripts default to `asia-south1` for compute and the repository-approved
`asia-southeast1` evidence location. Changing evidence location is a data
residency decision, not only a performance choice.

## 1. Create the GCP foundation

From the repository root:

```powershell
.\deploy\gcp\bootstrap.ps1 -ProjectId himath-unique-project-2026
```

The command is idempotent. It enables the required APIs, creates the registry,
service identities, private buckets, and empty Secret Manager resources. It
refuses to change anything while billing is disabled.

## 2. Fill the secrets

Run the helper once for each value. It reads the value without placing it in
the command line or shell history.

```powershell
$kinds = @(
  'database-url',
  'database-url-direct',
  'clerk-secret-key',
  'clerk-publishable-key',
  'party-identifier-key',
  'party-blind-index-key',
  'api-cursor-signing-key'
)
$kinds | ForEach-Object {
  .\deploy\gcp\set-secret.ps1 -ProjectId himath-unique-project-2026 -Kind $_
}
```

`party-identifier-key` must be a Fernet key. Generate it locally from the
backend environment with:

```powershell
Set-Location backend
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Set-Location ..
```

Use independently generated random values for `party-blind-index-key` and
`api-cursor-signing-key`. Never reuse the Fernet key for either purpose.

## 3. Deploy

Use the exact HTTPS issuer shown by Clerk:

```powershell
.\deploy\gcp\deploy.ps1 `
  -ProjectId himath-unique-project-2026 `
  -ClerkIssuer https://YOUR-CLERK-FRONTEND-API
```

The script builds immutable images, runs Alembic as a job, deploys API and web,
then patches the API's exact CORS and Clerk authorized-party origins. Finally it
deploys the landing page and one background worker instance. It prints all
three public URLs.

Evidence uploads are disabled by default. That is intentional: the storage
service requires the bucket region, retention, access, deletion terms, and
approval to be recorded first. After that approval exists, deploy with:

```powershell
.\deploy\gcp\deploy.ps1 `
  -ProjectId himath-unique-project-2026 `
  -ClerkIssuer https://YOUR-CLERK-FRONTEND-API `
  -ApproveRealDataStorage
```

The document AI/provider approval is a separate gate and remains false. The
deployment must not accept real evidence for model processing until the terms
required by the backend service plans are recorded.

## 4. Give a teammate deployment access

```powershell
.\deploy\gcp\grant-team-member.ps1 `
  -ProjectId himath-unique-project-2026 `
  -Email teammate@example.com
```

This grants deployment, build, log-reading, and service-account impersonation
permissions. Build-source access is restricted to its own private bucket. It
does not grant Project Owner, the broad Project Viewer role, IAM administration,
access to client evidence, or access to secret values other than the Clerk
publishable key required during the frontend build.

If the teammate only needs to view the application, do not run this command;
send the application URL and invite them through Clerk instead.

## 5. Domains

First validate the generated `run.app` URLs. For production domains, put the
three services behind a global external Application Load Balancer with managed
certificates and route, for example:

- `draftly.example` to `draftly-landing-production`;
- `app.draftly.example` to `draftly-web-production`;
- `api.draftly.example` to `draftly-api-production`.

Then rebuild the frontend with the public API URL and update the API's
`ALLOWED_ORIGINS` and `CLERK_AUTHORIZED_PARTY` to the final app origin. Update
Clerk's allowed origins/redirect URLs as well. A load balancer and DNS records
are not created by these scripts because the actual domains and DNS owner are
not known.

## Operational checks

```powershell
gcloud run services list --region asia-south1 --project himath-unique-project-2026
gcloud run jobs executions list --job draftly-migrate-preview --region asia-south1 --project himath-unique-project-2026
gcloud beta run worker-pools describe draftly-worker-preview --region asia-south1 --project himath-unique-project-2026
gcloud run services logs read draftly-api-preview --region asia-south1 --project himath-unique-project-2026 --limit 50
```

The repository currently has a continuous outbox worker but no implemented
scheduler entrypoint. No scheduled Cloud Run job is claimed here until that
runner exists.
