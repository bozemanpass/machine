from digitalocean import Domain, Manager, Project, SSHKey
from machine.types import TAG_MACHINE_TYPE_PREFIX, TAG_MACHINE_CREATED


def projectFromName(manager: Manager, name: str) -> Project:
    projects = manager.get_all_projects()
    for project in projects:
        if project.name == name:
            return project
    return None


def sshKeyFromName(manager: Manager, name: str) -> SSHKey:
    keys = manager.get_all_sshkeys()
    for key in keys:
        if key.name == name:
            return key
    return None


def dnsRecordIdFromName(domain: Domain, name: str) -> str:
    records = domain.get_records()
    for record in records:
        if record.name == name:
            return record.id
    return None


def get_machine_type(droplet):
    type = next((t for t in droplet.tags if TAG_MACHINE_TYPE_PREFIX in t), "").replace(TAG_MACHINE_TYPE_PREFIX, "")
    if not type:
        return None
    return type


def is_machine_created(droplet):
    return TAG_MACHINE_CREATED in droplet.tags
