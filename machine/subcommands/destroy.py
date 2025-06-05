import click
import digitalocean

from machine.di import d
from machine.log import debug, fatal_error, output
from machine.util import dnsRecordIdFromName, is_machine_created
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
@click.argument("droplet-ids", nargs=-1)
@click.pass_context
def command(context, confirm, delete_dns, all, droplet_ids):
    command_context: MainCmdCtx = context.obj
    config = command_context.config
    manager = digitalocean.Manager(token=config.access_token)
    for droplet_id in droplet_ids:
        try:
            droplet = manager.get_droplet(droplet_id)
        except digitalocean.NotFoundError:
            fatal_error(f"Error: machine with id {droplet_id} not found")
        name = droplet.name

        if not is_machine_created(droplet) and not all:
            fatal_error(f'ERROR: Cannot destroy droplet "{name}" (id: {droplet.id}), it was not created by machine.')

        if not is_same_session(command_context, droplet) and not all:
            fatal_error(
                f'ERROR: Cannot destroy droplet "{name}" (id: {droplet.id}), it was created by a different session of machine.'
            )

        if confirm:
            output(
                "Type YES (not y or yes or Yes) to confirm that you want to permanently"
                f' DELETE/DESTROY droplet "{name}" (id: {droplet.id})'
            )
            confirmation = input()
            if confirmation != "YES":
                fatal_error("Destroy operation aborted, not confirmed by user")
        result = droplet.destroy()

        if result and delete_dns and config.dns_zone:
            zone = config.dns_zone
            if d.opt.debug:
                debug(f"Deleting host record {name}.{zone}")
            domain = digitalocean.Domain(token=config.access_token, name=zone)
            if not domain:
                fatal_error(f"Error: Domain {domain} does not exist, machine destroyed but DNS record not removed")
            record_id = dnsRecordIdFromName(domain, name)
            if record_id:
                if d.opt.debug:
                    debug(f"Deleting dns record id={record_id}")
                domain.delete_domain_record(id=record_id)
            else:
                if d.opt.debug:
                    debug(f"No dns record found for {name}.{zone}")

        if not result:
            fatal_error("Error destroying machine")
