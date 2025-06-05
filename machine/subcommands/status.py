import click
import json
import requests

from machine.log import output
from machine.subcommands.list import get_droplets
from machine.types import MainCmdCtx


def print_normal(statuses):
    for status in statuses:
        output(
            f"{status['name']} ({status['id']}):\t" + "\t".join([f"{k}={v}" for k, v in status.items() if k not in ["name", "id"]])
        )


def print_json(statuses):
    output(json.dumps(statuses))


@click.command(help="Machine status")
@click.option("--id", metavar="<MACHINE-ID>", help="Filter by id")
@click.option("--name", "-n", metavar="<MACHINE-NAME>", help="Filter by name")
@click.option("--tag", "-t", metavar="<TAG-TEXT>", help="Filter by tag")
@click.option("--type", "-m", metavar="<MACHINE-TYPE>", help="Filter by type")
@click.option("--region", "-r", metavar="<REGION>", help="Filter by region")
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.option("--status-check", metavar="<CHECK>", default="cloud-init-status", help="Status check to perform")
@click.option(
    "--all",
    is_flag=True,
    default=False,
    help="All machines, including those not created by this tool or by other sessions",
)
@click.option("--quiet", "-q", is_flag=True, default=False, help="Only display machine IDs")
@click.pass_context
def command(context, id, name, tag, type, region, all, output, quiet, status_check):
    command_context: MainCmdCtx = context.obj

    droplets = get_droplets(command_context, id, name, tag, type, region, all)

    statuses = []
    for d in droplets:
        status = {"name": d.name, "id": d.id, "droplet-status": d.status, status_check: "UNKNOWN"}
        try:
            r = requests.get(f"http://{d.ip_address}:4242/cgi-bin/{status_check}")
            if 200 == r.status_code:
                status[status_check] = r.json()["status"]
        except:  # noqa: E722
            pass
        statuses.append(status)

    if output == "json":
        print_json(statuses)
    else:
        print_normal(statuses)
