from expandvars import expand

from machine.types import MachineConfig
from machine.util import Manager, sshKeyFromName


def get_user_data(manager: Manager, ssh_key_name: str, fqdn: str, machine_config: MachineConfig):
    if not fqdn:
        fqdn = ""

    script_args = machine_config.script_args
    if not script_args:
        script_args = ""

    ssh_key = sshKeyFromName(manager, ssh_key_name)
    ssh_public_key = ssh_key.public_key
    escaped_args = script_args.replace('"', '\\"')

    cloud_env = {
        "MACHINE_SCRIPT_URL": machine_config.script_url,
        "MACHINE_SCRIPT_DIR": machine_config.script_dir,
        "MACHINE_FQDN": fqdn,
    }

    # Exand here because otherwise escaping the vars properly for nested scripts is a guessing game
    escaped_args = expand(escaped_args, environ=cloud_env)
    cloud_config = f"""#cloud-config
users:
  - name: {machine_config.new_user_name}
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh-authorized-keys:
      - {ssh_public_key}
"""
    if machine_config.script_url and machine_config.script_dir and machine_config.script_path:
        cloud_config += f"""
runcmd:
  - mkdir -p {machine_config.script_dir}
  - curl -L {machine_config.script_url} -o {machine_config.script_path}
  - chmod +x {machine_config.script_path}
  - [su, -c, "env {' '.join([f"{k}='{v}'" for k, v in cloud_env.items()])} {machine_config.script_path} {escaped_args}", -, {machine_config.new_user_name}]
"""
    return cloud_config
