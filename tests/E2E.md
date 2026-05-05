# End-to-End Tests

These tests verify that `machine` can create and manage real VMs on a cloud provider, including DNS record lifecycle. They are **not** run as part of the normal test suite due to cost and runtime.

Tests can be run against **DigitalOcean**, **Vultr**, or **GCP** by setting the `E2E_PROVIDER` environment variable.

## Prerequisites

### DigitalOcean

You need a DigitalOcean account with:

- An API token with the required permissions (see below)
- An SSH key registered in the account
- A DNS zone managed by DigitalOcean (e.g. `example.com`). Note that Vultr does not have full DNS hosting functionality: it only supports hosting second-level domains, not subdomains (irrespective of what their documentation states). So `example.com` works but `test.example.com` does not.
- A project to assign droplets to

#### API Token Permissions

The DigitalOcean API token must be a **custom token** with these scopes enabled:

| Scope | Access | Used for |
|---|---|---|
| `droplet` | read, create, delete | Creating, listing, and destroying test droplets |
| `ssh_key` | read | Looking up SSH keys by name |
| `domain` | read, create, delete | Creating and removing DNS A records |
| `project` | read, update | Listing projects and assigning droplets to them |
| `tag` | read, create | Tagging droplets by type and custom tags |

A full-access read/write token will also work, but a scoped token is recommended.

### Vultr

You need a Vultr account with:

- An API key (from https://my.vultr.com/settings/#settingsapi)
- An SSH key registered in the account
- A DNS zone managed by Vultr (e.g. `example.com`)

The Vultr API key has full access by default; there is no scope configuration.

### GCP

You need a GCP project with:

- Compute Engine API and Cloud DNS API enabled
- Billing configured (Cloud DNS requires it)
- A Cloud DNS managed zone you control (e.g. `gcp.example.com`)
- An SSH key entry in project metadata (the `ssh-key` config value matches the username portion — see the main README's GCP Config section)
- Either Application Default Credentials set up locally (`gcloud auth application-default login`) or a service account JSON key file (referenced via `E2E_GCP_CREDENTIALS_FILE`)

If you use a service account, it needs at minimum:

| Role | Used for |
|---|---|
| `roles/compute.instanceAdmin.v1` | Create, list, destroy VMs and read project SSH keys |
| `roles/dns.admin` | Create and remove DNS A records |

## Environment Variables

### Provider Selection

| Variable | Required | Description |
|---|---|---|
| `E2E_PROVIDER` | No | Provider to test: `digital-ocean` (default), `vultr`, or `gcp` |

### Common (all providers)

| Variable | Required | Description |
|---|---|---|
| `E2E_SSH_KEY` | Yes | Name of an SSH key registered with the provider |
| `E2E_REGION` | No | Region slug (default: provider-specific, see below) |
| `E2E_IMAGE` | No | Image slug or ID (default: provider-specific, see below) |
| `E2E_SIZE` | No | Instance size (default: provider-specific, see below) |

### DigitalOcean

| Variable | Required | Description |
|---|---|---|
| `E2E_DO_TOKEN` | Yes | DigitalOcean API token |
| `E2E_DO_DNS_ZONE` | Yes | DNS zone hosted at DigitalOcean (e.g. `do.example.com`) |
| `E2E_PROJECT` | Yes | DO project to assign droplets to |

Defaults: region `nyc1`, image `ubuntu-24-04-x64`, size `s-1vcpu-512mb-10gb`

### Vultr

| Variable | Required | Description |
|---|---|---|
| `E2E_VULTR_API_KEY` | Yes | Vultr API key |
| `E2E_VULTR_DNS_ZONE` | Yes | DNS zone hosted at Vultr (e.g. `example.com` — must be a second-level domain) |

Defaults: region `ewr`, image `2136` (Ubuntu 24.04), size `vc2-1c-1gb`

### GCP

| Variable | Required | Description |
|---|---|---|
| `E2E_GCP_PROJECT_ID` | Yes | GCP project ID where test resources are created |
| `E2E_GCP_DNS_ZONE` | Yes | DNS zone hosted in Cloud DNS (e.g. `gcp.example.com`) |
| `E2E_GCP_CREDENTIALS_FILE` | No | Path to a service account JSON key file. If unset, [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) are used |

Defaults: region (zone) `us-central1-a`, image `projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64`, size `e2-micro`

## Running

### DigitalOcean

```bash
export E2E_DO_TOKEN="dop_v1_..."
export E2E_SSH_KEY="my-ssh-key"
export E2E_DO_DNS_ZONE="do.example.com"
export E2E_PROJECT="my-project"

make test-e2e
# Or directly
uv run pytest tests/test_e2e.py -v -m e2e
```

### Vultr

```bash
export E2E_PROVIDER="vultr"
export E2E_VULTR_API_KEY="..."
export E2E_SSH_KEY="my-ssh-key"
export E2E_VULTR_DNS_ZONE="example.com"

make test-e2e
# Or directly
uv run pytest tests/test_e2e.py -v -m e2e
```

### GCP

```bash
export E2E_PROVIDER="gcp"
export E2E_GCP_PROJECT_ID="my-gcp-project-12345"
export E2E_SSH_KEY="alice"
export E2E_GCP_DNS_ZONE="gcp.example.com"
# Optional: point at a service account JSON key. Otherwise ADC is used:
#   gcloud auth application-default login
# export E2E_GCP_CREDENTIALS_FILE="$HOME/.config/gcloud/sa.json"

make test-e2e
# Or directly
uv run pytest tests/test_e2e.py -v -m e2e
```

The normal `make test` (and CI) will **skip** these tests automatically.

## CI

The GitHub Actions workflow (`.github/workflows/e2e-test.yml`) runs e2e tests for each provider in parallel using a matrix strategy. Each provider run requires its own credentials configured in the `e2e` GitHub environment:

| Provider | Secrets | Variables |
|---|---|---|
| DigitalOcean | `E2E_DO_TOKEN` | `E2E_SSH_KEY`, `E2E_DO_DNS_ZONE`, `E2E_PROJECT` |
| Vultr | `E2E_VULTR_API_KEY` | `E2E_SSH_KEY`, `E2E_VULTR_DNS_ZONE` |
| GCP | *(none yet — see note below)* | `E2E_SSH_KEY`, `E2E_GCP_PROJECT_ID`, `E2E_GCP_DNS_ZONE` |

**GCP in CI**: the workflow passes `E2E_GCP_PROJECT_ID` and `E2E_GCP_DNS_ZONE` through, but does not yet wire up service account credentials (delivering a JSON key file from a secret needs extra workflow steps). Until that's added, the GCP matrix cell will skip with "credentials not configured" — set up to be addressed in a future change.

If credentials for a provider are not configured, that provider's test run will be skipped automatically.

## What's Tested

- **Instance lifecycle** — create, list, destroy
- **DNS lifecycle** — create with `--update-dns`, verify A record, destroy with `--delete-dns`
- **Cloud-init initialization** — create with `--type`, verify type tag
- **Custom tags** — create with `--tag`, verify tag filtering

## Cleanup

Each test cleans up after itself. All test instances use unique names prefixed with `e2etest-` so they are easy to identify.

## Cost

Tests use the smallest available instance size and destroy VMs immediately after verification, so cost is minimal.
