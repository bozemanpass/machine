# machine
CLI utility to create and manage VMs

Supports [DigitalOcean](https://www.digitalocean.com/), [Vultr](https://www.vultr.com/), and [Google Cloud Platform](https://cloud.google.com/) hosting platforms.

## Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and builds.

Install uv:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Development Setup

```
uv sync
```

This creates a `.venv` virtual environment and installs all dependencies (including dev tools like ruff).

Run the CLI during development:
```
uv run machine --help
```

Run the linter:
```
uv run ruff check machine/
```

## Build

Build a self-contained executable using [shiv](https://github.com/linkedin/shiv):
```
./sh/build-package.sh
```

This produces `build/machine`, a single-file Python zipapp.

## Install

Install directly from the GitHub repository using uv:
```
uv tool install git+https://github.com/stirlingbridge/machine.git
```

Alternatively, download the `machine` binary from the [releases page](https://github.com/stirlingbridge/machine/releases), make it executable, and place it on your PATH:
```
chmod +x machine
sudo mv machine /usr/local/bin/
```

## Usage

### Config File
Access token and other settings configured in the file `~/.machine/config.yml`. The config file contains a provider section (`digital-ocean`, `vultr`, or `gcp`) and a `machines` section.

If only one provider section is present, it is auto-detected. If multiple provider sections exist, add a `provider:` key to select one explicitly:

```yaml
provider: vultr
```

#### DigitalOcean Config

```yaml
digital-ocean:
    access-token: dop_v1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ssh-key: my-ssh-key-name
    dns-zone: example.com
    machine-size: s-4vcpu-8gb
    image: ubuntu-22-04-x64
    region: nyc3
    project: Infrastructure

machines:
    example:
        new-user-name: alice
        script-dir: /opt/setup-scripts
        script-url: https://raw.githubusercontent.com/example/setup-machine.sh
        script-path: /opt/setup-scripts/setup-machine.sh
        script-args: "-y"
```

| Key | Required | Description |
|-----|----------|-------------|
| `access-token` | Yes | DigitalOcean API access token |
| `ssh-key` | Yes | Name of the SSH key in your DigitalOcean account to use for new machines |
| `dns-zone` | No | DNS zone for automatic DNS record creation/deletion |
| `machine-size` | Yes | Default machine size slug (e.g. `s-4vcpu-8gb`) |
| `image` | Yes | Default image name (e.g. `ubuntu-22-04-x64`) |
| `region` | Yes | Default region code (e.g. `nyc3`) |
| `project` | No | DigitalOcean project name to assign new machines to |

Supported regions: `NYC1`, `NYC3`, `AMS3`, `SFO2`, `SFO3`, `SGP1`, `LON1`, `FRA1`, `TOR1`, `BLR1`, `SYD1`

#### Vultr Config

```yaml
vultr:
    api-key: ${VULTR_API_KEY}
    ssh-key: my-ssh-key-name
    dns-zone: example.com
    machine-size: vc2-1c-1gb
    image: 2136
    region: ewr

machines:
    example:
        new-user-name: alice
        script-dir: /opt/setup-scripts
        script-url: https://raw.githubusercontent.com/example/setup-machine.sh
        script-path: /opt/setup-scripts/setup-machine.sh
        script-args: "-y"
```

| Key | Required | Description |
|-----|----------|-------------|
| `api-key` | Yes | Vultr API key (from https://my.vultr.com/settings/#settingsapi) |
| `ssh-key` | Yes | Name of the SSH key in your Vultr account to use for new machines |
| `dns-zone` | No | DNS zone for automatic DNS record creation/deletion |
| `machine-size` | Yes | Vultr plan slug (e.g. `vc2-1c-1gb`). Use `machine list-plans` or the Vultr API to list available plans |
| `image` | Yes | Vultr OS ID (numeric, e.g. `2136` for Ubuntu 24.04). Use `machine list-os` or the Vultr API to list available OS IDs |
| `region` | Yes | Vultr region code (e.g. `ewr`) |

Supported regions: `ewr`, `ord`, `dfw`, `sea`, `lax`, `atl`, `ams`, `lhr`, `fra`, `sjc`, `syd`, `nrt`, `cdg`, `icn`, `mia`, `sgp`, `sto`, `mex`, `mad`, `sao`, `del`, `hnl`, `yto`, `blr`, `jnb`, `bom`, `tlv`

**Note:** Vultr does not have a "projects" concept, so the `project` config key and the `projects` command are not applicable when using the Vultr provider.

#### GCP Config

```yaml
gcp:
    project-id: my-gcp-project
    credentials-file: ~/.config/gcloud/service-account.json
    ssh-key: alice
    dns-zone: example.com
    machine-size: e2-standard-2
    image: projects/debian-cloud/global/images/family/debian-12
    region: us-central1-a
```

| Key | Required | Description |
|-----|----------|-------------|
| `project-id` | Yes | GCP project ID where all resources (VMs, DNS, etc.) live |
| `credentials-file` | No | Path to a service account JSON key file. If omitted, [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) are used (e.g. from `gcloud auth application-default login`) |
| `ssh-key` | Yes | Username GCP associates with an SSH key in the project's `ssh-keys` metadata (see SSH key notes below) |
| `dns-zone` | No | DNS name of a [Cloud DNS](https://cloud.google.com/dns) managed zone (e.g. `example.com`) |
| `machine-size` | Yes | GCE machine type (e.g. `e2-standard-2`) |
| `image` | Yes | Image self-link or family path (e.g. `projects/debian-cloud/global/images/family/debian-12`) |
| `region` | Yes | GCE *zone* (e.g. `us-central1-a`). Despite the key name, GCP requires a fully-qualified zone, not a region |

**SSH keys:**

GCP doesn't have a named SSH key registry like DigitalOcean or Vultr. Instead, public keys live in the project's `ssh-keys` metadata, and each one is associated with a username. The value of `ssh-key` in the config must match one of those usernames.

Two ways to add a key:

1. **Console** (Compute Engine → Metadata → SSH Keys → Add SSH Key): paste a raw public key, e.g.
   ```
   ssh-rsa AAAAB3Nza... alice@laptop
   ```
   GCP derives the username from the comment portion at the end — everything before the first `@`. So `alice@laptop` and `alice@example.com` both produce the username `alice`. Set `ssh-key: alice` in the config.

2. **gcloud** — write each line in the explicit `<username>:<key>` form to a file (no auto-derivation here), then upload:
   ```
   echo "alice:ssh-rsa AAAAB3Nza... alice@laptop" > keys.txt
   gcloud compute project-info add-metadata --metadata-from-file ssh-keys=keys.txt
   ```

The tool reads existing keys but does not create them.

**Other notes:**
- The `project` config key and re-assignment to projects are not applicable when using GCP — every resource is owned by the project specified in `project-id` at creation time.
- The `region` field is interpreted as a GCE zone. Validation only checks for plausibility; any zone string with a hyphen is accepted.

#### Machines Section

**machines section:**

Each entry under `machines:` defines a machine type that can be referenced with `create --type`:

| Key | Required | Description |
|-----|----------|-------------|
| `new-user-name` | Yes | Username for the non-root user created on the machine |
| `script-url` | No | URL to download an initialization script from |
| `script-dir` | No | Directory to store the initialization script |
| `script-path` | No | Full path for the initialization script |
| `script-args` | No | Arguments passed to the initialization script (supports variable expansion) |

If `script-url`, `script-dir`, and `script-path` are all provided, the script is downloaded and executed as the new user during cloud-init. The following variables are available for expansion in `script-args`:

- `$MACHINE_SCRIPT_URL` — URL of the initialization script
- `$MACHINE_SCRIPT_DIR` — directory path for the script
- `$MACHINE_FQDN` — fully qualified domain name of the machine (if DNS is configured)

#### Environment Variable Substitution

Config values support environment variable substitution using `${VAR}` syntax, similar to Docker Compose files. This is useful for keeping secrets like API tokens out of the config file.

Supported forms:
- `${VAR}` — substitutes the value of `VAR`; errors if the variable is not set
- `${VAR:-default}` — substitutes the value of `VAR`, or `default` if the variable is not set

Examples:
```yaml
# DigitalOcean
digital-ocean:
    access-token: ${DO_API_TOKEN}
    ssh-key: ${SSH_KEY_NAME:-my-ssh-key}
    dns-zone: example.com
    machine-size: ${MACHINE_SIZE:-s-4vcpu-8gb}
    image: ubuntu-22-04-x64
    region: ${DO_REGION:-nyc3}
    project: Infrastructure
```

```yaml
# Vultr
vultr:
    api-key: ${VULTR_API_KEY}
    ssh-key: ${SSH_KEY_NAME:-my-ssh-key}
    dns-zone: example.com
    machine-size: ${MACHINE_SIZE:-vc2-1c-1gb}
    image: 2136
    region: ${VULTR_REGION:-ewr}
```

Substitution is applied to all string values throughout the config file, including the `machines` section.

#### Advanced Machine Setup

Examples of advanced machine setup scripts can be found in [the machine-provisioning repository](https://github.com/bozemanpass/machine-provisioning).

### Session Management

Each invocation of `machine` uses a session ID (auto-generated and stored in `~/.machine/session-id.yml`). Machines are tagged with their session ID on creation. By default, `list`, `status`, `list-domain`, and `destroy` only operate on machines from the current session. Use the `--all` flag to include machines from other sessions or machines not created by this tool.

The session ID can be overridden with the global `--session-id` option.

### Automatic Tagging

Machines created by this tool are automatically tagged with:

- `machine:created` — identifies the machine as created by this tool
- `machine:type:<type-name>` — the machine type from the config
- `machine:session:<session-id>` — the session that created the machine

### Global Options
```
$ machine --help
Usage: machine [OPTIONS] COMMAND [ARGS]...

Options:
  --debug               Enable debug output
  --quiet               Suppress all non-essential output
  --verbose             Enable verbose output
  --dry-run             Run but do not do anything
  --config-file <PATH>  Specify the config file (default
                        ~/.machine/config.yml)
  --session-id <ID>     Override the default session ID
  -h, --help            Show this message and exit.

Commands:
  create       Create a machine
  destroy      Destroy one or more machines
  domains      List dns domains
  list         List machines
  list-domain  List domain records
  projects     List projects
  ssh-keys     List ssh keys
  status       Machine status
  types        List configured machine types
  version      Display version
```

### Commands

#### create

Create a new machine on the configured provider. By default, the machine is initialized with cloud-init (using the specified `--type` from config) and a DNS A record is created.

```
$ machine create --help
Usage: machine create [OPTIONS]

  Create a machine

Options:
  -n, --name <MACHINE-NAME>         Name for new machine  [required]
  -t, --tag <TAG-TEXT>              Tag to be applied to new machine
  -m, --type <MACHINE-TYPE>        Machine type from config (required if --initialize)
  -r, --region <REGION-CODE>       Region (overrides config default)
  -s, --machine-size <MACHINE-SLUG>
                                    Machine size (overrides config default)
  -s, --image <IMAGE-NAME>         Image (overrides config default)
  --wait-for-ip / --no-wait-for-ip Wait for IP address assignment (default: off)
  --update-dns / --no-update-dns   Create DNS A record (default: on)
  --initialize / --no-initialize   Initialize with cloud-init (default: on)
  -o, --output <FORMAT>            Output format (json)
  -h, --help                       Show this message and exit.
```

Output formats:
- Default: human-readable status messages
- `--output json`: JSON object with id, name, tags, region, ip, type

JSON output example:
```json
{
  "id": "12345678",
  "name": "my-machine",
  "tags": ["machine:created", "machine:type:example", "machine:session:abc12345"],
  "region": "nyc3",
  "ip": "203.0.113.10",
  "type": "example"
}
```

When `--update-dns` is enabled (the default), the command waits for the instance's IP address and creates an A record in the configured `dns-zone` with a 5-minute TTL.

When `--initialize` is enabled (the default), a cloud-config user-data payload is generated that creates a non-root user with sudo access, installs the SSH key, and optionally downloads and runs an initialization script.

If a `project` is configured (DigitalOcean only), the machine is automatically assigned to that project.

#### destroy

Destroy one or more machines by instance ID. By default, requires confirmation and deletes associated DNS records.

```
$ machine destroy --help
Usage: machine destroy [OPTIONS] [MACHINE-IDS]...

  Destroy one or more machines

Options:
  --confirm / --no-confirm       Require confirmation (default: on)
  --delete-dns / --no-delete-dns Delete associated DNS records (default: on)
  --all                          Include machines not created by this tool
                                 or by other sessions
  -h, --help                     Show this message and exit.
```

Confirmation requires typing exactly `YES` (not "y", "yes", or "Yes"). Use `--no-confirm` to skip.

Safety checks prevent destroying machines that were not created by this tool or that belong to a different session, unless `--all` is specified.

#### list

List machines with optional filtering.

```
$ machine list --help
Usage: machine list [OPTIONS]

  List machines

Options:
  --id <MACHINE-ID>       Filter by id
  -n, --name <MACHINE-NAME>  Filter by name
  -t, --tag <TAG-TEXT>    Filter by tag
  -m, --type <MACHINE-TYPE>  Filter by type
  -r, --region <REGION>   Filter by region
  -o, --output <FORMAT>   Output format (json)
  -q, --quiet             Only display machine IDs
  --unique                Return an error if more than one match
  --all                   Include all machines from all sessions
  -h, --help              Show this message and exit.
```

Output formats:
- Default: `name (id, region, type): ip_address`
- `--quiet`: machine IDs only
- `--output json`: JSON array of machine objects

JSON output example:
```json
[
  {
    "id": "12345678",
    "name": "my-machine",
    "tags": ["machine:created", "machine:type:example", "machine:session:abc12345"],
    "region": "nyc3",
    "ip": "203.0.113.10",
    "type": "example"
  }
]
```

#### status

Check the status of machines, including querying a custom status endpoint.

```
$ machine status --help
Usage: machine status [OPTIONS]

  Machine status

Options:
  --id <MACHINE-ID>          Filter by id
  -n, --name <MACHINE-NAME>  Filter by name
  -t, --tag <TAG-TEXT>       Filter by tag
  -m, --type <MACHINE-TYPE>  Filter by type
  -r, --region <REGION>      Filter by region
  -o, --output <FORMAT>      Output format (json)
  --status-check <CHECK>     Status check to perform (default: cloud-init-status)
  -q, --quiet                Only display machine IDs
  --all                      Include all machines from all sessions
  -h, --help                 Show this message and exit.
```

Output formats:
- Default: human-readable status line
- `--output json`: JSON array of status objects

JSON output example:
```json
[
  {
    "name": "my-machine",
    "id": "12345678",
    "machine-status": "active",
    "cloud-init-status": "done"
  }
]
```

In addition to the provider-reported instance status, this command queries each machine at `http://<ip>:4242/cgi-bin/<status-check>` (default: `cloud-init-status`) for custom status information. If the endpoint is unreachable, the status is reported as `UNKNOWN`.

#### list-domain

List DNS records within a domain zone.

```
$ machine list-domain --help
Usage: machine list-domain [OPTIONS] [ZONE]

  List domain records

Options:
  -n, --name <RECORD-NAME>  Filter by record name
  -m, --type <RECORD-TYPE>  Filter by record type (default: A and AAAA, use * for all)
  -o, --output <FORMAT>     Output format (json)
  -q, --quiet               Only display record names
  --all                     Include all records from all sessions
  -h, --help                Show this message and exit.
```

If `ZONE` is omitted, uses the `dns-zone` from config. By default, only shows A and AAAA records associated with machines from the current session.

Output formats:
- Default: `name\ttype\tdata`
- `--quiet`: record names only
- `--output json`: JSON array of record objects

JSON output example:
```json
[
  {
    "id": "98765432",
    "machine": {
      "id": "12345678",
      "name": "my-machine",
      "tags": ["machine:created"],
      "region": "nyc3",
      "ip": "203.0.113.10",
      "type": "example"
    },
    "name": "my-machine",
    "fqdn": "my-machine.example.com",
    "zone": "example.com",
    "data": "203.0.113.10",
    "ttl": 300,
    "type": "A"
  }
]
```

#### domains

List all DNS domains in your provider account.

Options:
- `-o, --output <FORMAT>`: Output format (`json`)

JSON output example:
```json
["example.com", "example.org"]
```

#### ssh-keys

List SSH keys in your provider account. Output format: `id: name (fingerprint)`

#### projects

List project names (DigitalOcean only).

Options:
- `-o, --output <FORMAT>`: Output format (`json`)

JSON output example:
```json
["Infrastructure", "Web Apps"]
```

#### types

List all machine types defined in the config file (from the `machines` section).

Options:
- `-o, --output <FORMAT>`: Output format (`json`)

JSON output example:
```json
["example", "webserver"]
```
