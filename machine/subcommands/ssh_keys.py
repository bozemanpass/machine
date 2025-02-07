import click
import digitalocean
from machine.log import output
from machine.types import MainCmdCtx


@click.command(help="List ssh keys")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    manager = digitalocean.Manager(token=command_context.config.access_token)
    my_keys = manager.get_all_sshkeys()
    for key in my_keys:
        output(f"{key.id}: {key.name} ({key.fingerprint})")
