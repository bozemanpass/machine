"""Tests for cloud-init user-data generation, including provisioning of
one or more SSH keys onto the new user."""

import pytest

from machine.cloud_config import get_user_data
from machine.factory import yaml
from machine.provider import SSHKey
from machine.types import MachineConfig


class FakeProvider:
    """Minimal CloudProvider stand-in that resolves a fixed set of keys."""

    provider_name = "Fake"
    _keys = {
        "alice": "ssh-rsa AAAAalice alice@host",
        "bob": "ssh-ed25519 AAAAbob bob@host",
    }

    def get_ssh_key(self, name):
        public_key = self._keys.get(name)
        if public_key is None:
            return None
        return SSHKey(id=name, name=name, fingerprint="", public_key=public_key)


def _machine_config():
    return MachineConfig("admin", None, None, None, None)


def _authorized_keys(user_data):
    """Parse generated user-data and return the new user's authorized keys."""
    parsed = yaml().load(user_data)
    return list(parsed["users"][0]["ssh-authorized-keys"])


class TestGetUserData:
    def test_single_key_installed(self):
        """The original single-name form installs exactly that key."""
        user_data = get_user_data(FakeProvider(), ["alice"], "", _machine_config())
        assert _authorized_keys(user_data) == ["ssh-rsa AAAAalice alice@host"]

    def test_multiple_keys_installed(self):
        """A list of names installs every resolved key, in order."""
        user_data = get_user_data(FakeProvider(), ["alice", "bob"], "host.example.com", _machine_config())
        assert _authorized_keys(user_data) == [
            "ssh-rsa AAAAalice alice@host",
            "ssh-ed25519 AAAAbob bob@host",
        ]

    def test_generated_user_data_is_valid_yaml(self):
        """Generated user-data must parse as YAML so cloud-init can consume it."""
        user_data = get_user_data(FakeProvider(), ["alice", "bob"], "", _machine_config())
        assert user_data.startswith("#cloud-config")
        parsed = yaml().load(user_data)
        assert parsed["users"][0]["name"] == "admin"

    def test_unknown_key_is_fatal(self):
        """A key name the provider cannot resolve aborts with a clear error."""
        with pytest.raises(SystemExit):
            get_user_data(FakeProvider(), ["alice", "ghost"], "", _machine_config())
