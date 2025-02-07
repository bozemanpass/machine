import click
import digitalocean
import time
from machine.config import get_machine
from machine.di import d
from machine.log import fatal_error, info, debug
from machine.types import MainCmdCtx, TAG_MACHINE_CREATED, TAG_MACHINE_TYPE_PREFIX
from machine.util import projectFromName, sshKeyFromName
from machine.cloud_config import get_user_data


def _validate_region(region: str):
    valid_regions = ["NYC1", "NYC3", "AMS3", "SFO2", "SFO3", "SGP1", "LON1", "FRA1", "TOR1", "BLR1", "SYD1"]
    if region is not None and region.upper() not in valid_regions:
        fatal_error(f"Error: region {region} is not one of {valid_regions}")


def _validate_image(image: str):
    valid_images = [
        "almalinux-8-x64",
        "almalinux-9-x64",
        "centos-stream-9-x64",
        "debian-11-x64",
        "debian-12-x64",
        "fedora-39-x64",
        "fedora-40-x64",
        "rockylinux-9-x64",
        "rockylinux-8-x64",
        "ubuntu-20-04-x64",
        "ubuntu-22-04-x64",
        "ubuntu-24-04-x64",
    ]
    if image is not None and image not in valid_images:
        info(f"Warning: image {image} is not one of these known valid images: {valid_images}")


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
@click.pass_context
def command(context, name, tag, type, region, machine_size, image, wait_for_ip, update_dns, initialize):
    command_context: MainCmdCtx = context.obj
    config = command_context.config

    if update_dns and not config.dns_zone:
        fatal_error("Error: DNS update requested but no zone configured")

    manager = digitalocean.Manager(token=command_context.config.access_token)

    if initialize:
        if not type:
            fatal_error("Error: a machine type must be supplied")
        machine_config = get_machine(type)
        if not machine_config:
            fatal_error(f"Error: machine type {type} is not defined")
        fqdn = f"{name}.{config.dns_zone}" if config.dns_zone else None
        user_data = get_user_data(manager, config.ssh_key, fqdn, machine_config)
        if d.opt.debug:
            info("user-data is:")
            info(user_data)

    ssh_key = sshKeyFromName(manager, config.ssh_key)

    _validate_region(region)
    _validate_image(image)

    tags = [
        TAG_MACHINE_TYPE_PREFIX + type.lower(),
        TAG_MACHINE_CREATED,
    ]
    if tag:
        tags.append(tag)

    droplet = digitalocean.Droplet(
        token=config.access_token,
        name=name,
        region=region if region is not None else config.region,
        image=image if image is not None else config.image,
        size_slug=machine_size if machine_size is not None else config.machine_size,
        ssh_keys=[ssh_key],
        tags=tags,
        user_data=user_data,
        backups=False,
    )
    # Create the droplet
    # This call returns nothing, it modifies the droplet object
    droplet.create()
    if droplet.id:
        if d.opt.quiet:
            print(f"{droplet.id}")
        else:
            print(f"New droplet created with id: {droplet.id}")
    # If requested, assign to a specified project
    if config.project:
        project_name = config.project
        project = projectFromName(manager, project_name)
        if not project:
            fatal_error(f"Error: Project {project_name} does not exist, machine created but not assigned to project")
        project.assign_resource([f"do:droplet:{droplet.id}"])
        if d.opt.verbose:
            info(f"Assigned droplet to project: {project}")
    # If requested, or if we are going to set a DNS record get the droplet's IPv4 address
    if wait_for_ip or update_dns:
        ip_address = None
        while not ip_address:
            time.sleep(1)
            droplet.load()
            ip_address = droplet.ip_address
            if d.opt.verbose:
                print("Waiting for droplet IP address")
        if d.opt.quiet:
            info(f"{ip_address}")
        else:
            info(f"IP Address: {ip_address}")
    # If requested, and we have the IP address, create a DNS host record for the droplet
    if update_dns and ip_address and config.dns_zone:
        zone = config.dns_zone
        host = name
        if d.opt.debug:
            debug(f"Setting host record {host}.{zone} to {ip_address}")
        domain = digitalocean.Domain(token=config.access_token, name=zone)
        if not domain:
            fatal_error(f"Error: Domain {domain} does not exist, machine created but DNS record not set")
        record = domain.create_new_domain_record(type="A", ttl=60 * 5, name=host, data=ip_address, tag=TAG_MACHINE_CREATED)
        if record:
            if d.opt.verbose:
                info(f"Created DNS record:{record}")
            if not d.opt.quiet:
                info(f"DNS: {host}.{zone}")
        else:
            fatal_error("Error: Failed to create DNS record")
