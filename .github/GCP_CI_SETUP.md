# GCP CI Setup (E2E Tests)

This document describes how to authenticate the GCP end-to-end test job in
GitHub Actions (`.github/workflows/e2e-test.yml`, the `gcp` matrix cell).

It uses **Workload Identity Federation (WIF)** — a keyless mechanism where
GitHub Actions presents a short-lived OIDC token that GCP exchanges for
short-lived credentials. No service-account JSON key is created, stored, or
rotated. This is the approach recommended by Google for CI.

If you have forked this repository and want the GCP e2e tests to run, follow
the steps below against your own GCP project.

## How it works

1. The workflow job requests an OIDC token from GitHub (`id-token: write`).
2. The `google-github-actions/auth` step sends that token to GCP's Security
   Token Service, which validates it against a **Workload Identity Pool
   provider** and returns short-lived credentials for a service account.
3. The action writes those credentials to a temp file and exports
   `GOOGLE_APPLICATION_CREDENTIALS`.
4. The `machine` GCP provider picks them up via Application Default
   Credentials (`google.auth.default()`), because `E2E_GCP_CREDENTIALS_FILE`
   is left unset in CI.

Two trust boundaries keep this scoped:

- The provider's **attribute condition** restricts which OIDC tokens are
  accepted (your GitHub org).
- The service account's **`principalSet://` IAM binding** restricts which of
  those accepted tokens may impersonate it (one specific repository).

## GCP project identifiers

GCP refers to a project three different ways. Using the wrong one is the most
common setup error:

| Identifier | Example | Where it is used |
|---|---|---|
| **Project ID** | `machine-testing-495021` | Most APIs, `gcloud --project=`, service-account email domains. Note: auto-generated IDs often end in digits — those digits are part of the ID, *not* the project number. |
| **Project number** | `433454590192` | WIF resource paths (`projects/<NUMBER>/locations/...`) and `principalSet://` IAM bindings only. |
| **Display name** | `machine-testing` | Console UI only. Never accepted as an API parameter. |

`gcloud projects list` shows the ID and number side by side.

## Prerequisites

A GCP project with:

- Compute Engine API and Cloud DNS API enabled
- Billing configured (Cloud DNS requires it)
- A Cloud DNS managed zone you control
- An SSH key entry in project metadata (see the main README's GCP section)
- `gcloud` installed and authenticated as a user with permission to manage
  IAM, service accounts, and workload identity pools

## Step 1 — GCP setup

Set these shell variables, then run the commands below. Adjust names to taste.

```bash
PROJECT_ID="your-e2e-project"          # the alphanumeric project ID
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
SA_NAME="machine-e2e"
POOL_ID="github"
PROVIDER_ID="github"
REPO="your-org/your-repo"              # the GitHub owner/repo, e.g. stirlingbridge/machine
REPO_OWNER="${REPO%%/*}"
```

### 1a. Service account and roles

The `machine` GCP provider creates instances on the `default` network and
manages Cloud DNS records. The minimal role set is:

| Role | Used for |
|---|---|
| `roles/compute.instanceAdmin.v1` | Create, list, destroy VMs; read project SSH-key metadata |
| `roles/dns.admin` | Create and remove DNS A records |

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="machine e2e tests"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

for role in roles/compute.instanceAdmin.v1 roles/dns.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" --role="$role"
done
```

### 1b. Workload Identity Pool

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" --location="global" \
  --display-name="GitHub Actions"
```

### 1c. OIDC provider

> **Watch the line continuations.** Each `\` must be the last character on its
> line. If a long line wraps in your terminal or editor without a `\`, gcloud
> will store a mangled multi-line value (see Troubleshooting).

The `--attribute-condition` is **required** by GCP — provider creation is
rejected without one. It is the trust boundary that limits which OIDC tokens
may even attempt authentication.

```bash
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository_owner == '${REPO_OWNER}'"
```

### 1d. Allow the repository to impersonate the service account

The `principalSet://` member narrows access to one specific repository (not
the whole org). Note this path uses the project **number**.

```bash
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO}"
```

To restrict further to a single branch, bind
`attribute.ref/refs/heads/main` instead of `attribute.repository/...`.

### 1e. Collect the values for GitHub

```bash
echo "E2E_GCP_WIF_PROVIDER=projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
echo "E2E_GCP_SERVICE_ACCOUNT=${SA_EMAIL}"
```

## Step 2 — GitHub repository configuration

Add the following as **variables** (not secrets — none of these are sensitive)
under the `e2e` environment: *Settings → Environments → e2e → Environment
variables*.

| Variable | Value |
|---|---|
| `E2E_GCP_WIF_PROVIDER` | `projects/<NUMBER>/locations/global/workloadIdentityPools/github/providers/github` (from step 1e) |
| `E2E_GCP_SERVICE_ACCOUNT` | `machine-e2e@<PROJECT_ID>.iam.gserviceaccount.com` (from step 1e) |
| `E2E_GCP_PROJECT_ID` | The alphanumeric project ID |
| `E2E_GCP_DNS_ZONE` | The **DNS name** of the managed zone (see note below) |

> **`E2E_GCP_DNS_ZONE` is the DNS name, not the managed-zone resource name.**
> In `gcloud dns managed-zones list`, use the value from the `DNS_NAME`
> column (e.g. `gcp.example.com`), not the `NAME` column. The provider matches
> managed zones by their DNS name. A trailing dot is optional.

## Step 3 — Workflow integration

`.github/workflows/e2e-test.yml` already contains the wiring; no changes are
needed when setting up a fork. For reference, it:

- Grants the job `permissions: id-token: write` (required for GitHub to mint
  the OIDC token — without it the auth step fails with a 403).
- Runs a `google-github-actions/auth@v2` step guarded by
  `if: matrix.provider == 'gcp'`, passing `E2E_GCP_WIF_PROVIDER` and
  `E2E_GCP_SERVICE_ACCOUNT`.
- Leaves `E2E_GCP_CREDENTIALS_FILE` unset, so the provider uses the
  Application Default Credentials that the auth step exported.

If any of the four variables is unset, the `gcp` matrix cell skips cleanly
instead of failing.

## Verifying

Confirm the IAM binding:

```bash
gcloud iam service-accounts get-iam-policy \
  machine-e2e@<PROJECT_ID>.iam.gserviceaccount.com
```

It should list the `principalSet://...` member against
`roles/iam.workloadIdentityUser`.

Confirm the provider:

```bash
gcloud iam workload-identity-pools providers describe github \
  --project="<PROJECT_ID>" --location="global" \
  --workload-identity-pool="github"
```

Each `attributeMapping` entry should be a single-line `assertion.*` value.

Then trigger a run from the Actions tab using the **workflow_dispatch**
button and watch the `gcp` matrix cell.

## Troubleshooting

**Mangled `attributeMapping` value.** If `describe` shows an entry as a YAML
block scalar (`|-`) split across lines, a long command line wrapped without a
`\` continuation. Do **not** delete the provider to fix it (see below). Repair
it in place with `update-oidc`, re-supplying the full corrected flags:

```bash
gcloud iam workload-identity-pools providers update-oidc github \
  --project="<PROJECT_ID>" --location="global" \
  --workload-identity-pool="github" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository_owner == '<REPO_OWNER>'"
```

**`ALREADY_EXISTS` when creating a pool or provider.** It was already created
(possibly by a failed earlier run). Use `update-oidc` / `update` to amend it
rather than recreating. Deletion of pools and providers is **soft**: the
resource is recoverable for 30 days, and during that window you **cannot**
create a new one with the same ID — so delete-and-recreate does not work as a
quick fix.

**Project ID vs. number.** WIF resource paths and `principalSet://` bindings
require the project *number*. Everything else (gcloud `--project=`, the
service-account email domain, `E2E_GCP_PROJECT_ID`) uses the alphanumeric
project *ID*. See the identifier table above.

**Auth step fails with a 403 / permission denied.** Check that the job has
`permissions: id-token: write`, that the provider's `attribute-condition`
matches your org, and that the `principalSet://` binding names your exact
`owner/repo`.
