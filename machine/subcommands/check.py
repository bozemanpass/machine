import click

from machine.log import output
from machine.types import MainCmdCtx


@click.command(help="Check config validity against the provider API")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    provider = command_context.provider
    cfg = command_context.config
    all_passed = True

    def report(check_name, passed, detail=""):
        nonlocal all_passed
        if not passed:
            all_passed = False
        status = "PASS" if passed else "FAIL"
        msg = f"  {status}: {check_name}"
        if detail:
            msg += f" ({detail})"
        output(msg)

    output(f"Checking config for provider: {provider.provider_name}")

    # 1. Check API token by making a simple read-only API call
    try:
        provider.list_ssh_keys()
        report("API authentication", True)
    except (Exception, SystemExit) as e:
        report("API authentication", False, str(e))
        # If auth fails, remaining checks will also fail
        output("\nAPI authentication failed, skipping remaining checks.")
        raise SystemExit(1)

    # 2. Check SSH keys exist
    if cfg.ssh_keys:
        for ssh_key_name in cfg.ssh_keys:
            key = provider.get_ssh_key(ssh_key_name)
            report("SSH key", key is not None, ssh_key_name)
    else:
        report("SSH key", False, "not configured")

    # 3. Check DNS zone exists
    if cfg.dns_zone:
        try:
            domains = provider.list_domains()
            found = cfg.dns_zone in domains
            report("DNS zone", found, cfg.dns_zone)
        except Exception as e:
            report("DNS zone", False, str(e))
    else:
        output("  SKIP: DNS zone (not configured)")

    # 4. Check project exists
    if cfg.project:
        try:
            projects = provider.list_projects()
            if projects:
                found = cfg.project in projects
                report("Project", found, cfg.project)
            else:
                output(f"  SKIP: Project (not supported by {provider.provider_name})")
        except Exception as e:
            report("Project", False, str(e))
    else:
        output("  SKIP: Project (not configured)")

    # 5. Validate region
    if cfg.region:
        try:
            provider.validate_region(cfg.region)
            report("Region", True, cfg.region)
        except SystemExit:
            report("Region", False, cfg.region)
    else:
        output("  SKIP: Region (not configured)")

    # 6. Validate image
    if cfg.image:
        try:
            provider.validate_image(cfg.image)
            report("Image", True, cfg.image)
        except SystemExit:
            report("Image", False, cfg.image)
    else:
        output("  SKIP: Image (not configured)")

    if all_passed:
        output("\nAll checks passed.")
    else:
        output("\nSome checks failed.")
        raise SystemExit(1)
