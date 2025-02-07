import click
import json
import digitalocean

from machine.log import fatal_error
from machine.types import MainCmdCtx, TAG_MACHINE_TYPE_PREFIX
from machine.util import get_machine_type, is_machine_created


def print_normal(droplets):
    for droplet in droplets:
        print(f"{droplet.name} ({droplet.id}, {droplet.region['slug']}, {get_machine_type(droplet)}): {droplet.ip_address}")


def print_quiet(droplets):
    for droplet in droplets:
        print(droplet.id)


def print_json(droplets):
    simplified = []
    for d in droplets:
        simple = {
            "id": d.id,
            "name": d.name,
            "tags": d.tags,
            "region": d.region["slug"],
            "ip": d.ip_address,
            "type": get_machine_type(d),
        }
        simplified.append(simple)
    print(json.dumps(simplified))


@click.command(help="List machines")
@click.option("--id", metavar="<MACHINE-ID>", help="Filter by id")
@click.option("--name", "-n", metavar="<MACHINE-NAME>", help="Filter by name")
@click.option("--tag", "-t", metavar="<TAG-TEXT>", help="Filter by tag")
@click.option("--type", "-m", metavar="<MACHINE-TYPE>", help="Filter by type")
@click.option("--region", "-r", metavar="<REGION>", help="Filter by region")
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.option(
    "--include-unmanaged",
    is_flag=True,
    default=False,
    help="Include machines not created by this tool",
)
@click.option("--quiet", "-q", is_flag=True, default=False, help="Only display machine IDs")
@click.option(
    "--unique",
    is_flag=True,
    default=False,
    help="Return an error if there is more than one match",
)
@click.pass_context
def command(context, id, name, tag, type, region, include_unmanaged, output, quiet, unique):
    command_context: MainCmdCtx = context.obj
    manager = digitalocean.Manager(token=command_context.config.access_token)

    droplets = []
    if id:
        droplet = manager.get_droplet(id)
        if droplet:
            droplets.append(droplet)
    elif name:
        droplets = manager.get_all_droplets(params={"name": name})
    elif tag:
        droplets = manager.get_all_droplets(tag_name=tag)
    elif type:
        droplets = manager.get_all_droplets(tag_name=TAG_MACHINE_TYPE_PREFIX + type.lower())
    else:
        droplets = manager.get_all_droplets()

    # we can't combine most filters over the API, so we also filter ourselves
    if name:
        droplets = filter(lambda d: d.name == name, droplets)

    if tag:
        droplets = filter(lambda d: tag in d.tags, droplets)

    if type:
        droplets = filter(lambda d: TAG_MACHINE_TYPE_PREFIX + type.lower() in d.tags, droplets)

    if region:
        droplets = filter(lambda d: region == d.region["slug"], droplets)

    if not include_unmanaged:
        droplets = filter(lambda d: is_machine_created(d), droplets)

    droplets = list(droplets)

    if unique and len(droplets) > 1:
        fatal_error(f"ERROR: --unique match required but {len(droplets)} matches found.")

    if output == "json":
        print_json(droplets)
    elif quiet:
        print_quiet(droplets)
    else:
        print_normal(droplets)
