import base64
import hashlib
import os

from machine.log import fatal_error, info
from machine.provider import CloudProvider, VM, SSHKey, DNSRecord


# Tags are stored as newline-separated values in instance metadata so that
# colon-bearing tag strings (e.g. "machine:created") round-trip unchanged.
_TAGS_METADATA_KEY = "machine-tags"
_USER_DATA_METADATA_KEY = "user-data"
_SSH_KEYS_METADATA_KEY = "ssh-keys"

_DEFAULT_OPERATION_TIMEOUT = 300

_GCP_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def _load_credentials(provider_config):
    creds_file = provider_config.get("credentials-file")
    if creds_file:
        from google.oauth2 import service_account

        path = os.path.expanduser(creds_file)
        return service_account.Credentials.from_service_account_file(path, scopes=_GCP_SCOPES)
    import google.auth

    creds, _ = google.auth.default(scopes=_GCP_SCOPES)
    return creds


def _fingerprint(public_key):
    parts = public_key.strip().split()
    if len(parts) < 2:
        return ""
    try:
        data = base64.b64decode(parts[1])
    except (ValueError, base64.binascii.Error):
        return ""
    digest = hashlib.md5(data).hexdigest()
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


def _parse_ssh_keys(raw):
    keys = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        user, key_data = line.split(":", 1)
        keys.append((user.strip(), key_data.strip()))
    return keys


class GcpProvider(CloudProvider):
    def __init__(self, provider_config):
        if "project-id" not in provider_config:
            fatal_error("Required key 'project-id' not found in 'gcp' section of config file")
        self._project = provider_config["project-id"]
        self._credentials = _load_credentials(provider_config)

        from google.cloud import compute_v1

        self._compute_v1 = compute_v1
        self._instances = compute_v1.InstancesClient(credentials=self._credentials)
        self._projects_client = compute_v1.ProjectsClient(credentials=self._credentials)
        self._dns_client = None

    def _dns(self):
        if self._dns_client is None:
            from google.cloud import dns

            self._dns_client = dns.Client(project=self._project, credentials=self._credentials)
        return self._dns_client

    @staticmethod
    def _parse_id(vm_id):
        if "/" not in vm_id:
            fatal_error(f"Error: GCP VM id must be in the form '<zone>/<name>', got: {vm_id}")
        zone, name = vm_id.split("/", 1)
        return zone, name

    @staticmethod
    def _make_id(zone, name):
        return f"{zone}/{name}"

    def _instance_to_vm(self, instance, zone) -> VM:
        ip_address = ""
        for nic in instance.network_interfaces:
            for ac in nic.access_configs:
                if ac.nat_i_p:
                    ip_address = ac.nat_i_p
                    break
            if ip_address:
                break

        tags = []
        if instance.metadata and instance.metadata.items:
            for item in instance.metadata.items:
                if item.key == _TAGS_METADATA_KEY and item.value:
                    tags = [t for t in item.value.split("\n") if t]
                    break

        return VM(
            id=self._make_id(zone, instance.name),
            name=instance.name,
            tags=tags,
            region=zone,
            ip_address=ip_address,
            status=instance.status,
        )

    def create_vm(self, name, region, image, size, ssh_key_name, tags, user_data) -> VM:
        zone = region
        if not self.get_ssh_key(ssh_key_name):
            fatal_error(f"Error: SSH key '{ssh_key_name}' not found in GCP project metadata")

        compute_v1 = self._compute_v1

        disk = compute_v1.AttachedDisk(
            boot=True,
            auto_delete=True,
            initialize_params=compute_v1.AttachedDiskInitializeParams(source_image=image),
        )
        access_config = compute_v1.AccessConfig(name="External NAT", type_="ONE_TO_ONE_NAT")
        nic = compute_v1.NetworkInterface(network="global/networks/default", access_configs=[access_config])

        metadata_items = []
        if tags:
            metadata_items.append(compute_v1.Items(key=_TAGS_METADATA_KEY, value="\n".join(tags)))
        if user_data:
            metadata_items.append(compute_v1.Items(key=_USER_DATA_METADATA_KEY, value=user_data))
        metadata = compute_v1.Metadata(items=metadata_items)

        instance = compute_v1.Instance(
            name=name,
            machine_type=f"zones/{zone}/machineTypes/{size}",
            disks=[disk],
            network_interfaces=[nic],
            metadata=metadata,
        )
        try:
            op = self._instances.insert(project=self._project, zone=zone, instance_resource=instance)
            op.result(timeout=_DEFAULT_OPERATION_TIMEOUT)
        except Exception as e:
            fatal_error(f"GCP API error creating VM: {e}")

        created = self._instances.get(project=self._project, zone=zone, instance=name)
        return self._instance_to_vm(created, zone)

    def get_vm(self, vm_id) -> VM:
        zone, name = self._parse_id(vm_id)
        try:
            inst = self._instances.get(project=self._project, zone=zone, instance=name)
        except Exception as e:
            fatal_error(f"Error: machine with id {vm_id} not found: {e}")
        return self._instance_to_vm(inst, zone)

    def destroy_vm(self, vm_id) -> bool:
        zone, name = self._parse_id(vm_id)
        try:
            op = self._instances.delete(project=self._project, zone=zone, instance=name)
            op.result(timeout=_DEFAULT_OPERATION_TIMEOUT)
        except Exception as e:
            msg = str(e)
            if "404" in msg or "notFound" in msg or "was not found" in msg:
                return True
            fatal_error(f"Error destroying machine {vm_id}: {e}")
        return True

    def list_vms(self, tag=None) -> list:
        request = self._compute_v1.AggregatedListInstancesRequest(project=self._project)
        agg = self._instances.aggregated_list(request=request)
        vms = []
        for zone_url, scoped in agg:
            zone = zone_url.rsplit("/", 1)[-1]
            instances = getattr(scoped, "instances", None) or []
            for inst in instances:
                vm = self._instance_to_vm(inst, zone)
                if tag is None or tag in vm.tags:
                    vms.append(vm)
        return vms

    def _get_project_metadata(self):
        proj = self._projects_client.get(project=self._project)
        return proj.common_instance_metadata

    def _get_project_ssh_keys_raw(self):
        meta = self._get_project_metadata()
        for item in meta.items or []:
            if item.key == _SSH_KEYS_METADATA_KEY:
                return item.value or ""
        return ""

    def get_ssh_key(self, name) -> SSHKey:
        for user, key_data in _parse_ssh_keys(self._get_project_ssh_keys_raw()):
            if user == name:
                return SSHKey(id=user, name=user, fingerprint=_fingerprint(key_data), public_key=key_data)
        return None

    def list_ssh_keys(self) -> list:
        return [
            SSHKey(id=u, name=u, fingerprint=_fingerprint(k), public_key=k)
            for u, k in _parse_ssh_keys(self._get_project_ssh_keys_raw())
        ]

    def _get_managed_zone(self, dns_zone):
        target = dns_zone if dns_zone.endswith(".") else dns_zone + "."
        for z in self._dns().list_zones():
            if z.dns_name == target:
                return z
        return None

    @staticmethod
    def _fqdn(name, zone):
        full = name if name.endswith("." + zone) or name == zone else f"{name}.{zone}"
        return full if full.endswith(".") else full + "."

    def create_dns_record(self, zone, record_type, name, data, ttl, tag=None) -> str:
        mz = self._get_managed_zone(zone)
        if not mz:
            info(f"Warning: DNS zone '{zone}' not found in GCP, DNS record not set")
            return None
        record_name = self._fqdn(name, zone)
        rrs = mz.resource_record_set(record_name, record_type, ttl, [data])
        change = mz.changes()
        change.add_record_set(rrs)
        try:
            change.create()
        except Exception as e:
            info(f"Warning: failed to create DNS record {record_name}: {e}")
            return None
        return record_name

    def delete_dns_record(self, zone, record_name) -> bool:
        mz = self._get_managed_zone(zone)
        if not mz:
            return False
        target = self._fqdn(record_name, zone)
        for rrs in mz.list_resource_record_sets():
            if rrs.name == target:
                change = mz.changes()
                change.delete_record_set(rrs)
                try:
                    change.create()
                except Exception:
                    return False
                return True
        return False

    def get_dns_records(self, zone) -> list:
        mz = self._get_managed_zone(zone)
        if not mz:
            info(f"Warning: DNS zone '{zone}' not found in GCP")
            return []
        records = []
        zone_suffix = "." + (zone if zone.endswith(".") else zone + ".")
        for rrs in mz.list_resource_record_sets():
            short_name = rrs.name
            if short_name.endswith(zone_suffix):
                short_name = short_name[: -len(zone_suffix)]
            elif short_name.endswith("."):
                short_name = short_name[:-1]
            records.append(
                DNSRecord(
                    id=rrs.name,
                    name=short_name,
                    type=rrs.record_type,
                    data=",".join(rrs.rrdatas),
                    ttl=rrs.ttl,
                )
            )
        return records

    def list_domains(self) -> list:
        return [z.dns_name.rstrip(".") for z in self._dns().list_zones()]

    def validate_region(self, region):
        if region is not None and "-" not in region:
            info(f"Warning: GCP zone '{region}' does not look like a valid zone (e.g. us-central1-a)")

    def validate_image(self, image):
        pass

    @property
    def provider_name(self) -> str:
        return "GCP"
