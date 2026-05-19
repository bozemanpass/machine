"""Tests for graceful handling of invalid user input."""

import os
import subprocess
import textwrap
import pytest


def run_machine(*args, env_override=None):
    """Run the machine CLI as a subprocess and return the result."""
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        ["uv", "run", "machine"] + list(args),
        capture_output=True,
        text=True,
        env=env,
    )
    return result


def write_config(path, content):
    with open(path, "w") as f:
        f.write(textwrap.dedent(content))


def valid_config():
    return """\
        digital-ocean:
          access-token: fake-token
          ssh-key: test-key
          machine-size: s-1vcpu-1gb
          image: ubuntu-22-04-x64
          region: nyc1
          project: test-project
        machines:
          web-server:
            new-user-name: admin
          db-server:
            new-user-name: dbadmin
        """


class TestInvalidMachineType:
    """Issue #29: invalid machine type should produce a graceful error, not a traceback."""

    @pytest.fixture()
    def config_dir(self, tmp_path):
        return tmp_path

    def test_invalid_machine_type_error_message(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(config_file, valid_config())
        result = run_machine(
            "--config-file",
            str(config_file),
            "create",
            "-n",
            "test-1",
            "-m",
            "nonexistent-type",
            "--no-update-dns",
        )
        assert result.returncode != 0
        assert "nonexistent-type" in result.stderr
        assert "not found" in result.stderr.lower()
        # Should list available types
        assert "web-server" in result.stderr
        assert "db-server" in result.stderr
        # Should NOT be a traceback
        assert "Traceback" not in result.stderr
        assert "KeyError" not in result.stderr

    def test_valid_machine_type_accepted(self, config_dir):
        """Verify that a valid machine type doesn't produce an error about the type.
        (It will fail later trying to reach DigitalOcean, but not with a type error.)"""
        config_file = config_dir / "config.yml"
        write_config(config_file, valid_config())
        result = run_machine(
            "--config-file",
            str(config_file),
            "create",
            "-n",
            "test-1",
            "-m",
            "web-server",
            "--no-update-dns",
        )
        # It will fail (no real DO token), but NOT because of machine type
        assert "not found in config" not in result.stderr


class TestMissingConfigSections:
    """Missing required config sections/keys should produce graceful errors."""

    @pytest.fixture()
    def config_dir(self, tmp_path):
        return tmp_path

    def test_missing_provider_section(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            machines:
              web-server:
                new-user-name: admin
            """,
        )
        result = run_machine("--config-file", str(config_file), "types")
        assert result.returncode != 0
        assert "digital-ocean" in result.stderr
        assert "vultr" in result.stderr
        assert "Traceback" not in result.stderr

    def test_missing_access_token(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              ssh-key: test-key
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              web-server:
                new-user-name: admin
            """,
        )
        result = run_machine("--config-file", str(config_file), "types")
        assert result.returncode != 0
        assert "access-token" in result.stderr
        assert "Traceback" not in result.stderr

    def test_missing_ssh_key(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: fake-token
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              web-server:
                new-user-name: admin
            """,
        )
        result = run_machine("--config-file", str(config_file), "types")
        assert result.returncode != 0
        assert "ssh-key" in result.stderr
        assert "Traceback" not in result.stderr

    def test_missing_machines_section(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: fake-token
              ssh-key: test-key
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            """,
        )
        result = run_machine("--config-file", str(config_file), "types")
        assert result.returncode != 0
        assert "machines" in result.stderr.lower()
        assert "Traceback" not in result.stderr

    def test_missing_new_user_name_in_machine(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: fake-token
              ssh-key: test-key
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              broken-machine:
                script-url: http://example.com/setup.sh
            """,
        )
        result = run_machine(
            "--config-file",
            str(config_file),
            "create",
            "-n",
            "test-1",
            "-m",
            "broken-machine",
            "--no-update-dns",
        )
        assert result.returncode != 0
        assert "new-user-name" in result.stderr
        assert "Traceback" not in result.stderr


class TestMultipleSshKeys:
    """Issue: the 'ssh-key' config value may be a single name or a list of
    names, and existing single-name configs must keep working."""

    @pytest.fixture()
    def config_dir(self, tmp_path):
        return tmp_path

    def test_single_ssh_key_still_accepted(self, config_dir):
        """The original scalar form must remain backwards compatible."""
        config_file = config_dir / "config.yml"
        write_config(config_file, valid_config())
        result = run_machine("--config-file", str(config_file), "types")
        assert result.returncode == 0
        assert "web-server" in result.stdout

    def test_list_of_ssh_keys_accepted(self, config_dir):
        """A YAML list of key names should parse without a config error."""
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: fake-token
              ssh-key:
                - first-key
                - second-key
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
            machines:
              web-server:
                new-user-name: admin
            """,
        )
        result = run_machine("--config-file", str(config_file), "types")
        assert result.returncode == 0
        assert "web-server" in result.stdout
        assert "Traceback" not in result.stderr

    def test_empty_ssh_key_list_rejected(self, config_dir):
        """An explicitly empty list is not a valid configuration."""
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: fake-token
              ssh-key: []
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
            machines:
              web-server:
                new-user-name: admin
            """,
        )
        result = run_machine("--config-file", str(config_file), "types")
        assert result.returncode != 0
        assert "ssh-key" in result.stderr
        assert "Traceback" not in result.stderr


class TestCreateNoInitialize:
    """--no-initialize should work without a machine type and without crashing."""

    @pytest.fixture()
    def config_dir(self, tmp_path):
        return tmp_path

    def test_no_initialize_without_type_no_crash(self, config_dir):
        """Using --no-initialize without --type should not crash with AttributeError or NameError."""
        config_file = config_dir / "config.yml"
        write_config(config_file, valid_config())
        result = run_machine(
            "--config-file",
            str(config_file),
            "create",
            "-n",
            "test-1",
            "--no-initialize",
            "--no-update-dns",
        )
        # It will fail (no real DO token), but should NOT crash with AttributeError/NameError
        # from the bugs where user_data was undefined and type.lower() was called on None
        assert "AttributeError" not in result.stderr
        assert "NameError" not in result.stderr
