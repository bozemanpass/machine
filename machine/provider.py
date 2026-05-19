from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VM:
    id: str
    name: str
    tags: list
    region: str
    ip_address: str
    status: str


@dataclass
class SSHKey:
    id: str
    name: str
    fingerprint: str
    public_key: str


@dataclass
class DNSRecord:
    id: str
    name: str
    type: str
    data: str
    ttl: int


class CloudProvider(ABC):
    @abstractmethod
    def create_vm(self, name, region, image, size, ssh_key_names, tags, user_data) -> VM:
        pass

    @abstractmethod
    def get_vm(self, vm_id) -> VM:
        pass

    @abstractmethod
    def destroy_vm(self, vm_id) -> bool:
        pass

    @abstractmethod
    def list_vms(self, tag=None) -> list:
        pass

    @abstractmethod
    def get_ssh_key(self, name) -> SSHKey:
        pass

    @abstractmethod
    def list_ssh_keys(self) -> list:
        pass

    @abstractmethod
    def create_dns_record(self, zone, record_type, name, data, ttl, tag=None) -> str:
        pass

    @abstractmethod
    def delete_dns_record(self, zone, record_name) -> bool:
        pass

    @abstractmethod
    def get_dns_records(self, zone) -> list:
        pass

    @abstractmethod
    def list_domains(self) -> list:
        pass

    def list_projects(self) -> list:
        return []

    def assign_to_project(self, project_name, vm_id):
        pass

    def validate_region(self, region):
        pass

    def validate_image(self, image):
        pass

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__
