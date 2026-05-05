import click
import json
import time

from machine.config import get_machine
from machine.di import d
from machine.log import fatal_error, info, debug, output as log_output
from machine.types import MainCmdCtx, TAG_MACHINE_CREATED, TAG_MACHINE_TYPE_PREFIX
from machine.cloud_config import get_user_data
from machine.util import vm_to_json_obj

from machine.types import TAG_MACHINE_SESSION_PREFIX


def _validate_dns_zone(provider, dns_zone):
    available_zones = provider.list_domains()
    if dns_zone not in available_zones:
        zones_str = ", ".join(available_zones) if available_zones else "none"
        fatal_error(f"Error: DNS zone '{dns_zone}' not found in {provider.provider_name}. Available zones: {zones_str}")


@click.command(help="Create a machine")
@click.option("--name", "-n", required=True, metavar="<MACHINE-NAME>", help="Name for new machine")
@click.option("--tag", "-t", metavar="<TAG-TEXT>", help="tag to be applied to new machine")
@click.option("--type", "-m", metavar="<MACHINE-TYPE>", help="create a machine of this type")
@click.option("--region", "-r", metavar="<REGION-CODE>", help="create a machine in this region (overrides default from config)")
@click.option(
    "--machine-size", "-s", metavar="<MACHINE-SLUG>", help="create a machine of this size (overrides default from config)"
)
@click.option("--image", "-s", metavar="<IMAGE-NAME>", help="create a machine from this image (overrides default from config)")
@click.option("--wait-for-ip/--no-wait-for-up", default=False)
@click.option("--update-dns/--no-update-dns", default=True)
@click.option("--initialize/--no-initialize", default=True)
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.pass_context
def command(context, name, tag, type, region, machine_size, image, wait_for_ip, update_dns, initialize, output):
    command_context: MainCmdCtx = context.obj
    config = command_context.config
    provider = command_context.provider

    if update_dns and not config.dns_zone:
        fatal_error("Error: DNS update requested but no zone configured")

    if update_dns and config.dns_zone:
        _validate_dns_zone(provider, config.dns_zone)

    user_data = None
    if initialize:
        if not type:
            fatal_error("Error: a machine type must be supplied")
        machine_config = get_machine(type)
        if not machine_config:
            fatal_error(f"Error: machine type {type} is not defined")
        fqdn = f"{name}.{config.dns_zone}" if config.dns_zone else None
        user_data = get_user_data(provider, config.ssh_key, fqdn, machine_config)
        if d.opt.debug:
            info("user-data is:")
            info(user_data)

    # Verify SSH key exists
    ssh_key = provider.get_ssh_key(config.ssh_key)
    if not ssh_key:
        fatal_error(f"Error: SSH key '{config.ssh_key}' not found in {provider.provider_name}")

    provider.validate_region(region)
    provider.validate_image(image)

    tags = [
        TAG_MACHINE_SESSION_PREFIX + command_context.session_id,
        TAG_MACHINE_CREATED,
    ]
    if type:
        tags.append(TAG_MACHINE_TYPE_PREFIX + type.lower())
    if tag:
        tags.append(tag)

    vm = provider.create_vm(
        name=name,
        region=region if region is not None else config.region,
        image=image if image is not None else config.image,
        size=machine_size if machine_size is not None else config.machine_size,
        ssh_key_name=config.ssh_key,
        tags=tags,
        user_data=user_data,
    )

    if vm.id:
        if output != "json":
            if d.opt.quiet:
                log_output(f"{vm.id}")
            else:
                log_output(f"New machine created with id: {vm.id}")

    # If requested, assign to a specified project
    if config.project:
        provider.assign_to_project(config.project, vm.id)
        if d.opt.verbose:
            info(f"Assigned machine to project: {config.project}")

    # If requested, or if we are going to set a DNS record get the VM's IPv4 address
    # Vultr returns "0.0.0.0" as main_ip while the instance is still pending,
    # so treat that the same as no IP assigned yet.
    ip_address = vm.ip_address if vm.ip_address != "0.0.0.0" else None
    if (wait_for_ip or update_dns) and not ip_address:
        while not ip_address:
            time.sleep(1)
            vm = provider.get_vm(vm.id)
            ip_address = vm.ip_address if vm.ip_address != "0.0.0.0" else None
            if d.opt.verbose:
                log_output("Waiting for machine IP address")
        if d.opt.quiet:
            info(f"{ip_address}")
        else:
            info(f"IP Address: {ip_address}")

    # If requested, and we have the IP address, create a DNS host record
    if update_dns and ip_address and config.dns_zone:
        zone = config.dns_zone
        host = name
        if d.opt.debug:
            debug(f"Setting host record {host}.{zone} to {ip_address}")
        record = provider.create_dns_record(
            zone=zone,
            record_type="A",
            name=host,
            data=ip_address,
            ttl=60 * 5,
            tag=TAG_MACHINE_CREATED,
        )
        if record:
            if d.opt.verbose:
                info(f"Created DNS record:{record}")
            if not d.opt.quiet:
                info(f"DNS: {host}.{zone}")

    if output == "json":
        log_output(json.dumps(vm_to_json_obj(vm)))
