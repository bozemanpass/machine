import os

import click

from machine import config
from machine import constants
from machine.di import d
from machine.log import fatal_error, output
from machine.providers import create_provider
from machine.subcommands import check, create, destroy, info, list, projects, ssh_keys, domains, list_domain, types, status
from machine.types import CliOptions, MainCmdCtx
from machine.util import load_session_id

CLICK_CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CLICK_CONTEXT_SETTINGS)
@click.option("--debug", is_flag=True, default=False, help="Enable debug output")
@click.option("--quiet", is_flag=True, default=False, help="Suppress all non-essential output")
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose output")
@click.option("--dry-run", is_flag=True, default=False, help="Run but do not do anything")
@click.option("--config-file", metavar="<PATH>", help=f"Specify the config file (default {constants.default_config_file_path})")
@click.option(
    "--session-id", metavar="<ID>", default=load_session_id, help="Override the default session ID (default: from session-id.yml)"
)
@click.pass_context
def main(context, debug, quiet, verbose, dry_run, config_file, session_id):
    options = CliOptions(debug, quiet, verbose, dry_run)
    d.opt = options
    # Skip config loading for version subcommand since it doesn't need it
    # and should work even when no config file exists (#25)
    if context.invoked_subcommand == "version":
        return
    cfg = config.get(config_file)
    provider = create_provider(cfg.provider_name, cfg.provider_config)
    main_context = MainCmdCtx(cfg, session_id, provider)
    context.obj = main_context


@main.command()
@click.pass_context
def version(context):
    try:
        version_file = os.path.join(os.path.dirname(__file__), "version.txt")
        with open(version_file) as f:
            version_string = f.read().strip()
    except FileNotFoundError:
        version_string = "dev"
    output(version_string)


main.add_command(check.command, "check")
main.add_command(create.command, "create")
main.add_command(destroy.command, "destroy")
main.add_command(domains.command, "domains")
main.add_command(info.command, "info")
main.add_command(list.command, "list")
main.add_command(list_domain.command, "list-domain")
main.add_command(projects.command, "projects")
main.add_command(ssh_keys.command, "ssh-keys")
main.add_command(types.command, "types")
main.add_command(status.command, "status")


def _provider_api_exception_types():
    """Base exception classes raised by the cloud provider SDKs on API failures.

    Collected lazily so importing this module (and the common DigitalOcean path)
    does not pull in every provider SDK up front.
    """
    import digitalocean
    from vultr import VultrException

    types = [digitalocean.Error, VultrException]
    try:
        from google.api_core import exceptions as google_api_exceptions
        from google.auth import exceptions as google_auth_exceptions

        types.append(google_api_exceptions.GoogleAPICallError)
        types.append(google_auth_exceptions.GoogleAuthError)
    except ImportError:
        pass
    return tuple(types)


def _friendly_provider_error(e) -> str:
    """Turn a raw provider SDK exception into a clear, actionable message."""
    detail = str(e).strip()
    lowered = detail.lower()
    auth_markers = (
        "unable to authenticate",
        "authentication",
        "unauthenticated",
        "unauthorized",
        "invalid api key",
        "permission",
        "forbidden",
        "401",
        "403",
    )
    if any(marker in lowered for marker in auth_markers):
        return (
            "Error: the cloud provider rejected the request as unauthenticated or unauthorized.\n"
            "Check that the API token/key in your config file is correct and has not expired."
        )
    return f"Error: cloud provider request failed: {detail}"


def cli():
    """Console-script entry point.

    Wraps the Click group so that errors raised by a provider's API (for
    example an expired or invalid access token) are reported as a clear
    message instead of an uncaught Python traceback (#95). Pass --debug to
    see the underlying traceback.
    """
    try:
        main()
    except _provider_api_exception_types() as e:
        if d.opt is not None and d.opt.debug:
            raise
        fatal_error(_friendly_provider_error(e))
