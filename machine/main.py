import click
from machine import config
from machine import constants
from machine.di import d
from machine.types import CliOptions, MainCmdCtx
from machine.subcommands import create, destroy, list, projects, ssh_keys, domains, list_domain

CLICK_CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CLICK_CONTEXT_SETTINGS)
@click.option("--debug", is_flag=True, default=False, help="Enable debug output")
@click.option("--quiet", is_flag=True, default=False, help="Suppress all non-essential output")
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose output")
@click.option("--dry-run", is_flag=True, default=False, help="Run but do not do anything")
@click.option("--config-file", metavar="<PATH>", help=f"Specify the config file (default {constants.default_config_file_path})")
@click.pass_context
def main(context, debug, quiet, verbose, dry_run, config_file):
    options = CliOptions(debug, quiet, verbose, dry_run)
    d.opt = options
    main_context = MainCmdCtx(config.get(config_file))
    context.obj = main_context


@main.command()
@click.pass_context
def version(context):
    print("Version command")


main.add_command(create.command, "create")
main.add_command(destroy.command, "destroy")
main.add_command(list.command, "list")
main.add_command(projects.command, "projects")
main.add_command(ssh_keys.command, "ssh-keys")
main.add_command(domains.command, "domains")
main.add_command(list_domain.command, "list-domain")
