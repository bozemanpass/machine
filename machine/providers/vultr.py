import base64
import time

from vultr import Vultr, VultrException

from machine.log import fatal_error, info
from machine.provider import CloudProvider, VM, SSHKey, DNSRecord


VALID_REGIONS = [
    "ewr", "ord", "dfw", "sea", "lax", "atl", "ams", "lhr", "fra",
    "sjc", "syd", "nrt", "cdg", "icn", "mia", "sgp", "sto",
    "mex", "mad", "sao", "del", "hnl", "yto", "blr", "jnb",
    "bom", "tlv",
]


def _instance_to_vm(instance) -> VM:
    return VM(
        id=instance.get("id", ""),
        name=instance.get("label", ""),
        tags=instance.get("tags", []),
        region=instance.get("region", ""),
        ip_address=instance.get("main_ip", ""),
        status=instance.get("status", ""),
    )


class VultrProvider(CloudProvider):
    def __init__(self, provider_config):
        info("WARNING: Vultr support is experimental and has not been fully verified. Use with caution.")
        if "api-key" not in provider_config:
            fatal_error("Required key 'api-key' not found in 'vultr' section of config file")
        self._api_key = provider_config["api-key"]
        self._client = Vultr(self._api_key)

    def create_vm(self, name, region, image, size, ssh_key_names, tags, user_data) -> VM:
        sshkey_ids = []
        for ssh_key_name in ssh_key_names:
            ssh_key = self._get_vultr_ssh_key(ssh_key_name)
            if not ssh_key:
                fatal_error(f"Error: SSH key '{ssh_key_name}' not found in Vultr")
            sshkey_ids.append(ssh_key["id"])

        kwargs = {
            "os_id": int(image),
            "label": name,
            "hostname": name,
            "sshkey_id": sshkey_ids,
            "tags": tags,
            "backups": "disabled",
        }
        if user_data:
            kwargs["user_data"] = base64.b64encode(user_data.encode()).decode()

        try:
            result = self._client.create_instance(region, size, **kwargs)
        except VultrException as e:
            fatal_error(f"Error creating instance: {e}")

        return _instance_to_vm(result)

    def get_vm(self, vm_id) -> VM:
        try:
            result = self._client.get_instance(vm_id)
        except VultrException as e:
            fatal_error(f"Error: machine with id {vm_id} not found: {e}")
        return _instance_to_vm(result)

    def destroy_vm(self, vm_id) -> bool:
        # Vultr returns HTTP 500 if the instance is still pending or locked
        # (e.g. during provisioning). Retry deletion with backoff.
        for attempt in range(24):
            try:
                self._client.delete_instance(vm_id)
                return True
            except VultrException as e:
                error_msg = str(e)
                if "500" in error_msg and ("not currently active" in error_msg or "currently locked" in error_msg):
                    info("Waiting for instance to become ready before destroying...")
                    time.sleep(5)
                elif "404" in error_msg:
                    return True  # already gone
                else:
                    fatal_error(f"Error: machine with id {vm_id} not found: {e}")
        fatal_error(f"Error: timed out waiting to destroy instance {vm_id}")
        return False

    def list_vms(self, tag=None) -> list:
        try:
            params = {"tag": tag} if tag else None
            result = self._client.list_instances(params=params)
        except VultrException as e:
            fatal_error(f"Error listing instances: {e}")
        return [_instance_to_vm(i) for i in result]

    def get_ssh_key(self, name) -> SSHKey:
        key = self._get_vultr_ssh_key(name)
        if not key:
            return None
        return SSHKey(
            id=key["id"],
            name=key["name"],
            fingerprint=key.get("fingerprint", ""),
            public_key=key.get("ssh_key", ""),
        )

    def list_ssh_keys(self) -> list:
        try:
            result = self._client.list_keys()
        except VultrException as e:
            fatal_error(f"Error listing SSH keys: {e}")
        return [
            SSHKey(
                id=k["id"],
                name=k["name"],
                fingerprint=k.get("fingerprint", ""),
                public_key=k.get("ssh_key", ""),
            )
            for k in result
        ]

    def create_dns_record(self, zone, record_type, name, data, ttl, tag=None) -> str:
        try:
            result = self._client.post(
                f"/domains/{zone}/records",
                type=record_type, name=name, data=data, ttl=ttl,
            )
        except VultrException:
            info(f"Warning: DNS zone '{zone}' not found in Vultr, DNS record not set")
            return None
        record = result.get("record", result)
        return record.get("id")

    def delete_dns_record(self, zone, record_name) -> bool:
        records = self.get_dns_records(zone)
        for record in records:
            if record.name == record_name:
                try:
                    self._client.delete(f"/domains/{zone}/records/{record.id}")
                except VultrException:
                    return False
                return True
        return False

    def get_dns_records(self, zone) -> list:
        try:
            result = self._client.get(f"/domains/{zone}/records")
        except VultrException:
            info(f"Warning: DNS zone '{zone}' not found in Vultr")
            return []
        records = result.get("records", [])
        return [
            DNSRecord(
                id=str(r.get("id", "")),
                name=r.get("name", ""),
                type=r.get("type", ""),
                data=r.get("data", ""),
                ttl=r.get("ttl", 0),
            )
            for r in records
        ]

    def list_domains(self) -> list:
        try:
            result = self._client.get("/domains")
        except VultrException as e:
            fatal_error(f"Error listing domains: {e}")
        domains = result.get("domains", [])
        return [d.get("domain", "") for d in domains]

    def validate_region(self, region):
        if region is not None and region.lower() not in VALID_REGIONS:
            fatal_error(f"Error: region {region} is not one of {VALID_REGIONS}")

    def validate_image(self, image):
        try:
            int(image)
        except (ValueError, TypeError):
            info(f"Warning: Vultr image (os_id) should be a numeric ID. Got: {image}")

    def _get_vultr_ssh_key(self, name):
        try:
            result = self._client.list_keys()
        except VultrException as e:
            fatal_error(f"Error listing SSH keys: {e}")
        for key in result:
            if key.get("name") == name:
                return key
        return None

    @property
    def provider_name(self) -> str:
        return "Vultr"
