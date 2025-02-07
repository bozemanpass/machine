import click
import digitalocean
import json

from machine.log import fatal_error
from machine.types import MainCmdCtx, TAG_MACHINE_CREATED


def print_normal(records, zone):
    for record in records:
        print(f"{record.name}\t{record.type}\t{record.data}")


def print_quiet(records):
    for record in records:
        print(record.name)


def print_json(records, droplets, zone):
    simplified = []
    for r in records:
        droplet_id = next((d.id for d in droplets if r.data == d.ip_address), None)
        simple = {
            "id": r.id,
            "droplet": droplet_id,
            "name": r.name,
            "data": r.data,
            "ttl": r.ttl,
            "type": r.type,
        }
        simplified.append(simple)
    print(json.dumps(simplified))


@click.command(help="List domain records")
@click.option("--name", "-n", metavar="<RECORD-NAME>", help="Filter by name")
@click.option("--type", "-m", metavar="<RECORD-TYPE>", help="Filter by type (default A and AAA)")
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.option("--quiet", "-q", is_flag=True, default=False, help="Only display machine IDs")
@click.option(
    "--include-unmanaged",
    is_flag=True,
    default=False,
    help="Include records not created by this tool",
)
@click.argument("zone", required=False)
@click.pass_context
def command(context, name, type, output, quiet, include_unmanaged, zone):
    command_context: MainCmdCtx = context.obj
    if not zone:
        zone = command_context.config.dns_zone
    if not zone:
        fatal_error("Error: no DNS zone specified.")
    domain = digitalocean.Domain(token=command_context.config.access_token, name=zone)
    records = domain.get_records()

    if type:
        if type != "*":
            records = filter(lambda r: r.type == type, records)
    else:
        records = filter(lambda r: r.type in ["A", "AAA", "AAAA"], records)

    droplets = []
    if not include_unmanaged:
        manager = digitalocean.Manager(token=command_context.config.access_token)
        droplets = manager.get_all_droplets(tag_name=TAG_MACHINE_CREATED)
        droplet_ips = [d.ip_address for d in droplets]
        records = filter(lambda r: r.data in droplet_ips, records)

    records = list(records)
    if output == "json":
        print_json(records, droplets, zone)
    elif quiet:
        print_quiet(records)
    else:
        print_normal(records, zone)
