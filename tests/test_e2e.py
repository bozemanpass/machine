"""End-to-end tests that create real VMs on a cloud provider.

These tests require a real cloud provider environment and are NOT run as part of
the normal test suite. They must be invoked explicitly:

    uv run pytest tests/test_e2e.py -v

Provider selection:
    E2E_PROVIDER    - Provider name: "digital-ocean" (default), "vultr", or "gcp"

Required environment variables (all providers):
    E2E_SSH_KEY     - Name of an SSH key already registered with the provider
Required environment variables (DigitalOcean):
    E2E_DO_TOKEN    - DigitalOcean API token
    E2E_DO_DNS_ZONE - DNS zone hosted at DigitalOcean (e.g. "do.example.com")
    E2E_PROJECT     - DO project name to assign droplets to

Required environment variables (Vultr):
    E2E_VULTR_API_KEY  - Vultr API key
    E2E_VULTR_DNS_ZONE - DNS zone hosted at Vultr (e.g. "example.com")

Required environment variables (GCP):
    E2E_GCP_PROJECT_ID      - GCP project ID where test resources are created
    E2E_GCP_DNS_ZONE        - DNS zone hosted in Cloud DNS (e.g. "gcp.example.com")
Optional (GCP):
    E2E_GCP_CREDENTIALS_FILE - Path to a service account JSON key file
                               (if unset, Application Default Credentials are used)

Optional environment variables:
    E2E_REGION      - Region slug (default: provider-specific)
    E2E_IMAGE       - Image slug or ID (default: provider-specific)
    E2E_SIZE        - Machine size slug (default: provider-specific)
"""

import json
import os
import subprocess
import uuid

import pytest


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

E2E_PROVIDER = os.environ.get("E2E_PROVIDER", "digital-ocean")

_PROVIDER_DEFAULTS = {
    "digital-ocean": {
        "region": "nyc1",
        "image": "ubuntu-24-04-x64",
        "size": "s-1vcpu-512mb-10gb",
    },
    "vultr": {
        "region": "ewr",
        "image": "2284",
        "size": "vc2-1c-1gb",
    },
    "gcp": {
        "region": "us-central1-a",
        "image": "projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64",
        "size": "e2-micro",
    },
}

_defaults = _PROVIDER_DEFAULTS.get(E2E_PROVIDER, _PROVIDER_DEFAULTS["digital-ocean"])

E2E_SSH_KEY = os.environ.get("E2E_SSH_KEY")

# Per-provider DNS zones
E2E_DO_DNS_ZONE = os.environ.get("E2E_DO_DNS_ZONE")
E2E_VULTR_DNS_ZONE = os.environ.get("E2E_VULTR_DNS_ZONE")
E2E_GCP_DNS_ZONE = os.environ.get("E2E_GCP_DNS_ZONE")

# Select the DNS zone for the active provider
if E2E_PROVIDER == "digital-ocean":
    E2E_DNS_ZONE = E2E_DO_DNS_ZONE
elif E2E_PROVIDER == "vultr":
    E2E_DNS_ZONE = E2E_VULTR_DNS_ZONE
elif E2E_PROVIDER == "gcp":
    E2E_DNS_ZONE = E2E_GCP_DNS_ZONE
else:
    E2E_DNS_ZONE = None
E2E_REGION = os.environ.get("E2E_REGION", _defaults["region"])
E2E_IMAGE = os.environ.get("E2E_IMAGE", _defaults["image"])
E2E_SIZE = os.environ.get("E2E_SIZE", _defaults["size"])

# Provider-specific credentials
E2E_DO_TOKEN = os.environ.get("E2E_DO_TOKEN")
E2E_PROJECT = os.environ.get("E2E_PROJECT")
E2E_VULTR_API_KEY = os.environ.get("E2E_VULTR_API_KEY")
E2E_GCP_PROJECT_ID = os.environ.get("E2E_GCP_PROJECT_ID")
E2E_GCP_CREDENTIALS_FILE = os.environ.get("E2E_GCP_CREDENTIALS_FILE")


# ---------------------------------------------------------------------------
# Skip the entire module if credentials are not provided
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.e2e

_MISSING = []
if not E2E_SSH_KEY:
    _MISSING.append("E2E_SSH_KEY")
if E2E_PROVIDER == "digital-ocean":
    if not E2E_DO_TOKEN:
        _MISSING.append("E2E_DO_TOKEN")
    if not E2E_DO_DNS_ZONE:
        _MISSING.append("E2E_DO_DNS_ZONE")
    if not E2E_PROJECT:
        _MISSING.append("E2E_PROJECT")
elif E2E_PROVIDER == "vultr":
    if not E2E_VULTR_API_KEY:
        _MISSING.append("E2E_VULTR_API_KEY")
    if not E2E_VULTR_DNS_ZONE:
        _MISSING.append("E2E_VULTR_DNS_ZONE")
elif E2E_PROVIDER == "gcp":
    if not E2E_GCP_PROJECT_ID:
        _MISSING.append("E2E_GCP_PROJECT_ID")
    if not E2E_GCP_DNS_ZONE:
        _MISSING.append("E2E_GCP_DNS_ZONE")
    # E2E_GCP_CREDENTIALS_FILE is optional — falls back to ADC.
else:
    _MISSING.append(f"E2E_PROVIDER (unknown provider: {E2E_PROVIDER})")

if _MISSING:
    pytestmark = [
        pytest.mark.e2e,
        pytest.mark.skip(reason=f"E2E env vars not set: {', '.join(_MISSING)}"),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_name(prefix="e2etest"):
    """Generate a short unique instance name safe for DNS."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _write_config(path, **overrides):
    """Write a minimal config file for the e2e test run."""
    if E2E_PROVIDER == "digital-ocean":
        cfg = {
            "access-token": E2E_DO_TOKEN,
            "ssh-key": E2E_SSH_KEY,
            "dns-zone": E2E_DNS_ZONE,
            "machine-size": E2E_SIZE,
            "image": E2E_IMAGE,
            "region": E2E_REGION,
            "project": E2E_PROJECT,
        }
        cfg.update(overrides)
        provider_lines = "\n".join(f"  {k}: {v}" for k, v in cfg.items())
        content = f"digital-ocean:\n{provider_lines}\nmachines:\n  e2e-basic:\n    new-user-name: e2euser\n"
    elif E2E_PROVIDER == "vultr":
        cfg = {
            "api-key": E2E_VULTR_API_KEY,
            "ssh-key": E2E_SSH_KEY,
            "dns-zone": E2E_DNS_ZONE,
            "machine-size": E2E_SIZE,
            "image": E2E_IMAGE,
            "region": E2E_REGION,
        }
        cfg.update(overrides)
        provider_lines = "\n".join(f"  {k}: {v}" for k, v in cfg.items())
        content = f"vultr:\n{provider_lines}\nmachines:\n  e2e-basic:\n    new-user-name: e2euser\n"
    elif E2E_PROVIDER == "gcp":
        cfg = {
            "project-id": E2E_GCP_PROJECT_ID,
            "ssh-key": E2E_SSH_KEY,
            "dns-zone": E2E_DNS_ZONE,
            "machine-size": E2E_SIZE,
            "image": E2E_IMAGE,
            "region": E2E_REGION,
        }
        if E2E_GCP_CREDENTIALS_FILE:
            cfg["credentials-file"] = E2E_GCP_CREDENTIALS_FILE
        cfg.update(overrides)
        provider_lines = "\n".join(f"  {k}: {v}" for k, v in cfg.items())
        content = f"gcp:\n{provider_lines}\nmachines:\n  e2e-basic:\n    new-user-name: e2euser\n"

    with open(path, "w") as f:
        f.write(content)


def run_machine(*args, config_file=None, session_id=None):
    """Run the machine CLI as a subprocess with the given arguments."""
    cmd = ["uv", "run", "machine"]
    if config_file:
        cmd += ["--config-file", str(config_file)]
    if session_id:
        cmd += ["--session-id", session_id]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result


def _extract_instance_id(output_text):
    """Extract the instance ID from CLI output like 'New machine created with id: 12345'.

    Handles both numeric IDs (DigitalOcean) and UUID IDs (Vultr).
    """
    for line in output_text.splitlines():
        if "id:" in line.lower():
            parts = line.split("id:")
            if len(parts) >= 2:
                candidate = parts[-1].strip()
                if candidate:
                    return candidate
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config_file(tmp_path_factory):
    """Write a config file that lives for the whole test module."""
    path = tmp_path_factory.mktemp("e2e") / "config.yml"
    _write_config(path)
    return path


@pytest.fixture(scope="module")
def session_id():
    """A unique session id shared across all tests in this module."""
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="class")
def instance(config_file, session_id):
    """Create a single instance with all features and destroy it after all tests.

    The instance is created with DNS, a machine type (cloud-init), a custom tag,
    and --wait-for-ip so that all aspects can be verified by individual tests.
    """
    name = _unique_name()
    custom_tag = f"e2e-tag-{uuid.uuid4().hex[:6]}"

    # ---- CREATE with all features ------------------------------------------
    result = run_machine(
        "create",
        "--name",
        name,
        "--type",
        "e2e-basic",
        "--update-dns",
        "--tag",
        custom_tag,
        "--wait-for-ip",
        config_file=config_file,
        session_id=session_id,
    )
    assert result.returncode == 0, f"create failed: {result.stderr}"
    create_out = result.stdout + result.stderr
    instance_id = _extract_instance_id(create_out)
    assert instance_id, f"Could not find instance id in output:\n{create_out}"

    info = {
        "name": name,
        "id": instance_id,
        "custom_tag": custom_tag,
        "create_out": create_out,
    }

    yield info

    # ---- TEARDOWN: destroy with DNS cleanup --------------------------------
    destroy_result = run_machine(
        "--verbose",
        "destroy",
        "--no-confirm",
        "--delete-dns",
        instance_id,
        config_file=config_file,
        session_id=session_id,
    )
    if destroy_result.returncode != 0:
        print(f"TEARDOWN WARNING: destroy exited {destroy_result.returncode}", flush=True)
        print(f"  stdout: {destroy_result.stdout}", flush=True)
        print(f"  stderr: {destroy_result.stderr}", flush=True)


# ---------------------------------------------------------------------------
# Tests — one instance, many assertions
# ---------------------------------------------------------------------------


class TestCheck:
    """Verify the ``check`` subcommand validates config against the provider API."""

    def test_check_passes_with_valid_config(self, config_file, session_id):
        """Verify that check succeeds when all config values are valid."""
        result = run_machine("check", config_file=config_file, session_id=session_id)
        combined = result.stdout + result.stderr
        assert result.returncode == 0, f"check failed: {combined}"
        assert "All checks passed" in combined

    def test_check_reports_api_auth_pass(self, config_file, session_id):
        """Verify that check reports API authentication as passing."""
        result = run_machine("check", config_file=config_file, session_id=session_id)
        combined = result.stdout + result.stderr
        assert "PASS: API authentication" in combined

    def test_check_reports_ssh_key_pass(self, config_file, session_id):
        """Verify that check reports the configured SSH key as found."""
        result = run_machine("check", config_file=config_file, session_id=session_id)
        combined = result.stdout + result.stderr
        assert "PASS: SSH key" in combined

    def test_check_reports_dns_zone_pass(self, config_file, session_id):
        """Verify that check reports the configured DNS zone as found."""
        result = run_machine("check", config_file=config_file, session_id=session_id)
        combined = result.stdout + result.stderr
        assert "PASS: DNS zone" in combined

    def test_check_fails_with_bad_token(self, tmp_path, session_id):
        """Verify that check fails when the provider rejects the credentials.

        For GCP there is no single "token" field — credentials come from a
        service account file or ADC. We simulate a similar failure by pointing
        at a project the credentials cannot access, which causes the first
        API call (list_ssh_keys) to fail with a permission error.
        """
        cfg_path = tmp_path / "config.yml"
        if E2E_PROVIDER == "digital-ocean":
            _write_config(cfg_path, **{"access-token": "invalid-token-for-e2e-test"})
        elif E2E_PROVIDER == "vultr":
            _write_config(cfg_path, **{"api-key": "invalid-token-for-e2e-test"})
        elif E2E_PROVIDER == "gcp":
            _write_config(cfg_path, **{"project-id": f"nonexistent-project-{uuid.uuid4().hex[:8]}"})
        result = run_machine("check", config_file=cfg_path, session_id=session_id)
        combined = result.stdout + result.stderr
        assert result.returncode != 0, f"check should have failed with bad token: {combined}"
        assert "FAIL: API authentication" in combined

    def test_check_fails_with_bad_ssh_key(self, tmp_path, session_id):
        """Verify that check fails when the SSH key does not exist at the provider."""
        cfg_path = tmp_path / "config.yml"
        _write_config(cfg_path, **{"ssh-key": f"nonexistent-key-{uuid.uuid4().hex[:8]}"})
        result = run_machine("check", config_file=cfg_path, session_id=session_id)
        combined = result.stdout + result.stderr
        assert result.returncode != 0, f"check should have failed with bad SSH key: {combined}"
        assert "FAIL: SSH key" in combined

    def test_check_fails_with_bad_dns_zone(self, tmp_path, session_id):
        """Verify that check fails when the DNS zone does not exist at the provider."""
        cfg_path = tmp_path / "config.yml"
        bogus_zone = f"bogus-{uuid.uuid4().hex[:8]}.example"
        _write_config(cfg_path, **{"dns-zone": bogus_zone})
        result = run_machine("check", config_file=cfg_path, session_id=session_id)
        combined = result.stdout + result.stderr
        assert result.returncode != 0, f"check should have failed with bad DNS zone: {combined}"
        assert "FAIL: DNS zone" in combined


class TestDnsZonePreFlight:
    """Verify that create fails fast when the configured DNS zone does not exist."""

    def test_create_fails_for_nonexistent_dns_zone(self, tmp_path, session_id):
        bogus_zone = f"bogus-{uuid.uuid4().hex[:8]}.example"
        cfg_path = tmp_path / "config.yml"
        _write_config(cfg_path, **{"dns-zone": bogus_zone})

        result = run_machine(
            "create",
            "--name",
            _unique_name(),
            "--type",
            "e2e-basic",
            "--no-initialize",
            "--update-dns",
            config_file=cfg_path,
            session_id=session_id,
        )
        assert result.returncode != 0, "Expected create to fail for nonexistent DNS zone"
        combined = result.stdout + result.stderr
        assert bogus_zone in combined, f"Error should mention the bogus zone '{bogus_zone}'"
        assert "not found" in combined.lower(), "Error should indicate zone was not found"


class TestInstanceLifecycle:
    """Create one instance with all features and verify each aspect independently.

    A single instance is created (via the class-scoped ``instance`` fixture) with
    DNS, a machine type, and a custom tag.  Each test method verifies a different
    aspect so that failures are reported individually.  The instance is destroyed
    automatically after all tests complete.
    """

    def test_instance_appears_in_list(self, instance, config_file, session_id):
        """Verify the instance shows up in ``list`` with the correct name."""
        result = run_machine(
            "list",
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"list failed: {result.stderr}"
        instances = json.loads(result.stdout)
        matched = [i for i in instances if str(i["id"]) == instance["id"]]
        assert len(matched) == 1, f"Expected 1 instance with id {instance['id']}, got {len(matched)}"
        assert matched[0]["name"] == instance["name"]

    def test_instance_has_ip(self, instance, config_file, session_id):
        """Verify the instance was assigned an IP address."""
        result = run_machine(
            "list",
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        instances = json.loads(result.stdout)
        matched = [i for i in instances if str(i["id"]) == instance["id"]]
        assert len(matched) == 1
        ip = matched[0]["ip"]
        assert ip is not None, "Instance has no IP address"
        assert ip != "0.0.0.0", "Instance IP is 0.0.0.0 (not yet assigned)"

    def test_dns_record_created(self, instance, config_file, session_id):
        """Verify that a DNS A record was created for the instance."""
        result = run_machine(
            "list-domain",
            "--name",
            instance["name"],
            "--output",
            "json",
            E2E_DNS_ZONE,
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"list-domain failed: {result.stderr}"
        records = json.loads(result.stdout)
        a_records = [r for r in records if r.get("name") == instance["name"] and r.get("type") == "A"]
        assert len(a_records) >= 1, f"No A record found for {instance['name']}.{E2E_DNS_ZONE}"

    def test_dns_zone_in_create_output(self, instance):
        """Verify that DNS zone was mentioned in the create output."""
        assert E2E_DNS_ZONE in instance["create_out"], f"DNS zone not mentioned in output:\n{instance['create_out']}"

    def test_type_tag_applied(self, instance, config_file, session_id):
        """Verify that the machine type tag was applied and is filterable."""
        result = run_machine(
            "list",
            "--type",
            "e2e-basic",
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        instances = json.loads(result.stdout)
        matched = [i for i in instances if str(i["id"]) == instance["id"]]
        assert len(matched) == 1, "Instance not found when filtering by type e2e-basic"
        assert matched[0]["type"] == "e2e-basic", "Type tag mismatch"

    def test_custom_tag_applied(self, instance, config_file, session_id):
        """Verify that the custom tag was applied and is filterable."""
        result = run_machine(
            "list",
            "--tag",
            instance["custom_tag"],
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        instances = json.loads(result.stdout)
        matched = [i for i in instances if str(i["id"]) == instance["id"]]
        assert len(matched) == 1, f"Instance not found with tag {instance['custom_tag']}"
