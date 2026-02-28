# Firebase Hosting + WIF Setup Guide

> Complete reference for the Firebase Hosting infrastructure powering lavinigam.com.
> Use this doc to replicate the setup on a new GCP project or troubleshoot issues.

## Current Configuration (as of 2026-02-28)

| Component | Value |
|-----------|-------|
| GCP Project ID | `kaggle-on-gcp` |
| GCP Project Number | `474775107710` |
| Firebase Hosting Site | `kaggle-on-gcp` (default site, URL: `kaggle-on-gcp.web.app`) |
| Custom Domain | `lavinigam.com` |
| Service Account | `github-actions-deploy@kaggle-on-gcp.iam.gserviceaccount.com` |
| WIF Pool | `github-pool` (global) |
| WIF Provider | `github-provider` (OIDC, issuer: `https://token.actions.githubusercontent.com`) |
| GitHub Repo | `lavinigam-gcp/lavinigam-ai-website` |
| GA4 Measurement ID | `G-T3N1WT63CL` |
| Hugo Version | `0.152.2` (extended) |

---

## Architecture Overview

```
GitHub Actions (push to main)
    │
    ├─ Build: Hugo --gc --minify → ./public artifact
    │
    └─ Deploy:
         ├─ google-github-actions/auth@v3 (WIF OIDC → access_token)
         └─ firebase deploy --only hosting (via GOOGLE_OAUTH_ACCESS_TOKEN)

Auth chain:
  GitHub OIDC Token
    → STS Exchange (WIF Pool/Provider)         [needs: roles/iam.workloadIdentityUser]
    → generateAccessToken (Service Account)    [needs: roles/iam.serviceAccountTokenCreator]
    → OAuth2 Bearer Token
    → Firebase CLI (GOOGLE_OAUTH_ACCESS_TOKEN)
    → Firebase Hosting API                     [needs: roles/firebasehosting.admin on SA]
```

---

## Step-by-Step Setup

### 1. GCP Project Prerequisites

```bash
# Set your project
export PROJECT_ID="kaggle-on-gcp"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  firebasehosting.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudresourcemanager.googleapis.com

# Ensure Firebase is initialized on the project (Blaze plan required)
# This must be done via Firebase Console: https://console.firebase.google.com
```

### 2. Create Service Account

```bash
export PROJECT_ID="kaggle-on-gcp"

gcloud iam service-accounts create github-actions-deploy \
  --display-name="GitHub Actions Deploy" \
  --project=$PROJECT_ID

# Grant Firebase Hosting Admin at project level
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --role="roles/firebasehosting.admin" \
  --member="serviceAccount:github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
```

### 3. Create Workload Identity Federation Pool + Provider

```bash
export PROJECT_ID="kaggle-on-gcp"

# Create the pool
gcloud iam workload-identity-pools create github-pool \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --project=$PROJECT_ID

# Create the OIDC provider
# IMPORTANT: Update the attribute-condition with your GitHub org/repo
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository=='lavinigam-gcp/lavinigam-ai-website'" \
  --project=$PROJECT_ID

# Get the full provider resource name (needed for GitHub secret WIF_PROVIDER)
gcloud iam workload-identity-pools providers describe github-provider \
  --workload-identity-pool="github-pool" \
  --location="global" \
  --project=$PROJECT_ID \
  --format="value(name)"
# Output: projects/474775107710/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

### 4. Bind WIF Principal to Service Account (TWO roles required)

> **CRITICAL**: Both roles are required. `workloadIdentityUser` allows federation/impersonation.
> `serviceAccountTokenCreator` allows generating OAuth2 access tokens (needed for `token_format: 'access_token'`).

```bash
export PROJECT_ID="kaggle-on-gcp"
export PROJECT_NUMBER="474775107710"
export GITHUB_REPO="lavinigam-gcp/lavinigam-ai-website"
export SA_EMAIL="github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
export MEMBER="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"

# Role 1: Allow WIF principal to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="$MEMBER" \
  --project=$PROJECT_ID

# Role 2: Allow WIF principal to generate access tokens
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.serviceAccountTokenCreator" \
  --member="$MEMBER" \
  --project=$PROJECT_ID
```

> **WARNING**: Always use the CLI for these commands, not the GCP Console.
> Copy-pasting the long `principalSet://` URI into Console text fields can introduce
> invisible whitespace that corrupts the member name. IAM silently accepts the corrupted
> member but it never matches the actual principal, causing 403 errors with no useful
> diagnostic. Use the `$MEMBER` variable approach above to avoid this.

#### Verify bindings are correct

```bash
gcloud iam service-accounts get-iam-policy $SA_EMAIL \
  --project=$PROJECT_ID --format=json | python3 -c "
import json, sys
policy = json.load(sys.stdin)
for b in policy.get('bindings', []):
    for m in b['members']:
        status = 'CORRUPTED' if '  ' in m else 'OK'
        print(f'{status} | {b[\"role\"]} | len={len(m)}')
"
```

Expected output (both len=162, both OK):
```
OK | roles/iam.serviceAccountTokenCreator | len=162
OK | roles/iam.workloadIdentityUser | len=162
```

### 5. Firebase Hosting Initialization

Files in the repo (not created by `firebase init`, managed manually):

**`.firebaserc`** — links to GCP project:
```json
{
  "projects": {
    "default": "kaggle-on-gcp"
  }
}
```

**`firebase.json`** — hosting config with security headers:
```json
{
  "hosting": {
    "site": "kaggle-on-gcp",
    "public": "public",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "cleanUrls": true,
    "trailingSlash": false,
    "headers": [
      {
        "source": "**",
        "headers": [
          { "key": "Strict-Transport-Security", "value": "max-age=31536000; includeSubDomains; preload" }
        ]
      },
      {
        "source": "**/*.html",
        "headers": [
          { "key": "Cache-Control", "value": "public, max-age=3600" },
          { "key": "X-Content-Type-Options", "value": "nosniff" },
          { "key": "X-Frame-Options", "value": "DENY" },
          { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
          { "key": "Permissions-Policy", "value": "geolocation=(), microphone=(), camera=(), payment=()" },
          { "key": "Content-Security-Policy", "value": "..." }
        ]
      },
      {
        "source": "**/*.{js,css,png,jpg,jpeg,gif,svg,ico,woff,woff2,eot,ttf,otf,webp}",
        "headers": [
          { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }
        ]
      }
    ]
  }
}
```

### 6. GitHub Secrets

Set these three secrets in the repo (Settings → Secrets → Actions):

| Secret | Value | Example |
|--------|-------|---------|
| `WIF_PROVIDER` | Full provider resource name | `projects/474775107710/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `WIF_SERVICE_ACCOUNT` | Service account email | `github-actions-deploy@kaggle-on-gcp.iam.gserviceaccount.com` |
| `GCP_PROJECT_ID` | GCP project ID | `kaggle-on-gcp` |

### 7. Connect Custom Domain

```bash
# Add domain to Firebase Hosting
firebase hosting:channel:deploy live --project=$PROJECT_ID  # or via Console

# Firebase Console: Hosting → Custom domains → Add custom domain → lavinigam.com
```

Then in your DNS provider (Squarespace for us):

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A | @ | `199.36.158.100` | 1h |
| TXT | @ | Firebase verification token | 1h |

> Firebase will provision an SSL certificate via ACME/Let's Encrypt after DNS propagates.
> This can take 10-60 minutes. Check status in Firebase Console → Hosting → Custom domains.

### 8. GitHub Actions Workflow

Key details in `.github/workflows/hugo.yml`:
- Uses `token_format: 'access_token'` because Firebase CLI's bundled `google-auth-library`
  does NOT support WIF "external_account" credential files
- Passes the access token as `GOOGLE_OAUTH_ACCESS_TOKEN` env var to `firebase deploy`
- Preview channels deploy on PRs (except Dependabot PRs which can't access secrets)
- `workflow_dispatch` enabled for manual triggers

---

## Changing the GCP Project ID

If you want to migrate from `kaggle-on-gcp` to a new project (e.g., `lavinigam-website`):

### GCP-side (new project)

```bash
export NEW_PROJECT_ID="lavinigam-website"
export NEW_PROJECT_NUMBER="<get from GCP Console>"
export GITHUB_REPO="lavinigam-gcp/lavinigam-ai-website"

# 1. Enable APIs
gcloud services enable \
  firebasehosting.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=$NEW_PROJECT_ID

# 2. Initialize Firebase on the new project (Console: firebase.google.com)
#    Must be on Blaze plan for Hosting custom domains

# 3. Create service account
gcloud iam service-accounts create github-actions-deploy \
  --display-name="GitHub Actions Deploy" \
  --project=$NEW_PROJECT_ID

# 4. Grant Firebase Hosting Admin
gcloud projects add-iam-policy-binding $NEW_PROJECT_ID \
  --role="roles/firebasehosting.admin" \
  --member="serviceAccount:github-actions-deploy@${NEW_PROJECT_ID}.iam.gserviceaccount.com"

# 5. Create WIF pool + provider
gcloud iam workload-identity-pools create github-pool \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --project=$NEW_PROJECT_ID

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'" \
  --project=$NEW_PROJECT_ID

# 6. Bind WIF principal to SA (BOTH roles)
export SA_EMAIL="github-actions-deploy@${NEW_PROJECT_ID}.iam.gserviceaccount.com"
export MEMBER="principalSet://iam.googleapis.com/projects/${NEW_PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"

gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="$MEMBER" \
  --project=$NEW_PROJECT_ID

gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.serviceAccountTokenCreator" \
  --member="$MEMBER" \
  --project=$NEW_PROJECT_ID

# 7. Get the new WIF provider resource name
gcloud iam workload-identity-pools providers describe github-provider \
  --workload-identity-pool="github-pool" \
  --location="global" \
  --project=$NEW_PROJECT_ID \
  --format="value(name)"

# 8. Connect custom domain in Firebase Console → Hosting → Custom domains
#    Update DNS records if Firebase assigns different IPs
```

### Repo-side changes

```bash
# 1. Update .firebaserc
sed -i '' 's/kaggle-on-gcp/NEW_PROJECT_ID/g' .firebaserc

# 2. Update firebase.json (site name)
sed -i '' 's/"site": "kaggle-on-gcp"/"site": "NEW_PROJECT_ID"/g' firebase.json

# 3. Update GitHub Secrets (Settings → Secrets → Actions)
#    - WIF_PROVIDER: new provider resource name (from step 7 above)
#    - WIF_SERVICE_ACCOUNT: new SA email
#    - GCP_PROJECT_ID: new project ID

# 4. Update GA4 if using a different property
#    - hugo.yaml: services.googleAnalytics.ID
```

### Files that reference the project ID

| File | What to change |
|------|---------------|
| `.firebaserc` | `projects.default` |
| `firebase.json` | `hosting.site` |
| GitHub Secrets | `WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`, `GCP_PROJECT_ID` |
| `hugo.yaml` | `services.googleAnalytics.ID` (only if GA4 property changes) |
| `.github/workflows/hugo.yml` | No changes needed (reads from secrets) |

---

## Troubleshooting

### "Failed to authenticate, have you run firebase login?"
Firebase CLI doesn't support WIF "external_account" credential files. Fix: use
`token_format: 'access_token'` in the auth step and pass as `GOOGLE_OAUTH_ACCESS_TOKEN`.

### "Permission 'iam.serviceAccounts.getAccessToken' denied"
Missing `roles/iam.serviceAccountTokenCreator` on the service account for the WIF principal.
Or the `principalSet://` member string is corrupted (extra whitespace from copy-paste).
Use the verification script in Step 4 above to check.

### "No site name or target name"
`firebase.json` is missing `"site": "PROJECT_ID"` in the hosting object.

### Hugo EOF front matter error
Content files must have valid YAML front matter enclosed in `---` delimiters.

### DNS / SSL issues
- Firebase needs an A record pointing to `199.36.158.100`
- TXT record for domain ownership verification
- SSL provisioning (ACME) can take up to 60 minutes after DNS propagates
- Check propagation: `dig A lavinigam.com +short` or dnschecker.org
- Squarespace: delete any conflicting forwarding rules before adding A records

### IAM propagation delay
IAM changes take 1-5 minutes to propagate globally. Don't re-run workflows
immediately after changing IAM bindings.
