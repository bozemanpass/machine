import click
import digitalocean
from machine.log import output
from machine.types import MainCmdCtx


@click.command(help="List dns domains")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    manager = digitalocean.Manager(token=command_context.config.access_token)
    my_domains = manager.get_all_domains()
    for domain in my_domains:
        output(f"{domain.name}")
