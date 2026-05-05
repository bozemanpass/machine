import os
import uuid

from machine.factory import yaml
from machine.constants import default_config_dir_path, default_session_id_file_path
from machine.types import TAG_MACHINE_TYPE_PREFIX, TAG_MACHINE_CREATED

from machine.types import MainCmdCtx, TAG_MACHINE_SESSION_PREFIX


def get_machine_type(vm):
    type = next((t for t in vm.tags if TAG_MACHINE_TYPE_PREFIX in t), "").replace(TAG_MACHINE_TYPE_PREFIX, "")
    if not type:
        return None
    return type


def is_machine_created(vm):
    return TAG_MACHINE_CREATED in vm.tags


def is_same_session(command_context: MainCmdCtx, vm):
    return TAG_MACHINE_SESSION_PREFIX + command_context.session_id in vm.tags


def load_session_id():
    if not os.path.exists(default_config_dir_path):
        os.makedirs(default_config_dir_path, exist_ok=True)

    if not os.path.exists(default_session_id_file_path):
        with open(default_session_id_file_path, "w") as f:
            f.write("id: " + str(uuid.uuid4()).replace("-", "")[0:8])

    sessionid_config = yaml().load(open(default_session_id_file_path, "r"))
    return sessionid_config["id"]


def vm_to_json_obj(vm):
    return {
        "id": vm.id,
        "name": vm.name,
        "tags": vm.tags,
        "region": vm.region,
        "ip": vm.ip_address,
        "type": get_machine_type(vm),
    }


def dns_record_to_json_obj(dns_record, zone, vm):
    if vm:
        vm = vm_to_json_obj(vm)

    return {
        "id": dns_record.id,
        "machine": vm,
        "name": dns_record.name,
        "fqdn": f"{dns_record.name}.{zone}",
        "zone": zone,
        "data": dns_record.data,
        "ttl": dns_record.ttl,
        "type": dns_record.type,
    }
