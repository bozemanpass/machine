import click

from machine.di import d
from machine.log import debug, fatal_error, output
from machine.util import is_machine_created
from machine.types import MainCmdCtx

from machine.util import is_same_session


@click.command(help="Destroy one or more machines")
@click.option("--confirm/--no-confirm", default=True)
@click.option("--delete-dns/--no-delete-dns", default=True)
@click.option(
    "--all",
    is_flag=True,
    default=False,
    help="Include machines not created by this tool",
)
@click.argument("machine-ids", nargs=-1)
@click.pass_context
def command(context, confirm, delete_dns, all, machine_ids):
    command_context: MainCmdCtx = context.obj
    config = command_context.config
    provider = command_context.provider

    for machine_id in machine_ids:
        vm = provider.get_vm(machine_id)
        name = vm.name

        if not is_machine_created(vm) and not all:
            fatal_error(f'ERROR: Cannot destroy machine "{name}" (id: {vm.id}), it was not created by this tool.')

        if not is_same_session(command_context, vm) and not all:
            fatal_error(
                f'ERROR: Cannot destroy machine "{name}" (id: {vm.id}), it was created by a different session.'
            )

        if confirm:
            output(
                "Type YES (not y or yes or Yes) to confirm that you want to permanently"
                f' DELETE/DESTROY machine "{name}" (id: {vm.id})'
            )
            confirmation = input()
            if confirmation != "YES":
                fatal_error("Destroy operation aborted, not confirmed by user")

        result = provider.destroy_vm(machine_id)

        if result and delete_dns and config.dns_zone:
            zone = config.dns_zone
            if d.opt.debug:
                debug(f"Deleting host record {name}.{zone}")
            deleted = provider.delete_dns_record(zone, name)
            if deleted:
                if d.opt.debug:
                    debug(f"Deleted dns record for {name}.{zone}")
            else:
                if d.opt.debug:
                    debug(f"No dns record found for {name}.{zone}")

        if not result:
            fatal_error("Error destroying machine")
