
from machine.types import MachineConfig
from machine.util import Manager, sshKeyFromName


def get_user_data(manager: Manager, ssh_key_name: str, machine_config: MachineConfig):

    ssh_key = sshKeyFromName(manager, ssh_key_name)
    ssh_public_key = ssh_key.public_key
    return f"""#cloud-config
users:
  - name: {machine_config.new_user_name}
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh-authorized-keys:
      - {ssh_public_key}
runcmd:
  - mkdir -p {machine_config.script_dir}
  - curl -L {machine_config.script_url} -o {machine_config.script_path}
  - chmod +x {machine_config.script_path}
  - su -c '{machine_config.script_path} {machine_config.script_args}' - {machine_config.new_user_name}
"""
