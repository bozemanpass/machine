import click
import digitalocean
from machine.log import output
from machine.types import MainCmdCtx


@click.command(help="List projects")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    manager = digitalocean.Manager(token=command_context.config.access_token)
    my_projects = manager.get_all_projects()
    for project in my_projects:
        output(f"{project.name}")
