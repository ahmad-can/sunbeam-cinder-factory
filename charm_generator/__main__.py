"""CLI entry point for the charm generator."""

import json
import logging
from pathlib import Path

import click

from charm_generator.generator import CharmGenerator, setup_logging
from charm_generator.validator import CharmValidator, compare_charms
from charm_generator.file_writer import CharmFileWriter
from charm_generator.settings import (
    DRIVER_SPECS_DIR,
    GENERATED_CHARMS_DIR,
    OPENAI_MODEL,
    get_settings_summary,
)


@click.group()
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Sunbeam Cinder Backend Charm Generator."""
    ctx.ensure_object(dict)
    setup_logging("DEBUG" if debug else "INFO")


@cli.command("generate")
@click.argument("spec_file")
@click.option("--output-dir", "-o", type=click.Path(), default=None)
@click.option("--overwrite/--no-overwrite", default=True)
@click.option("--model", type=str, default=None, help=f"OpenAI model (default: {OPENAI_MODEL})")
@click.option("--dry-run", is_flag=True, default=False)
@click.pass_context
def generate(ctx: click.Context, spec_file: str, output_dir: str | None, overwrite: bool, model: str | None, dry_run: bool) -> None:
    """Generate a charm from a driver specification file."""
    spec_path = Path(spec_file)
    
    if not spec_path.exists():
        # Try as a bare filename in the specs directory
        test_path = DRIVER_SPECS_DIR / spec_file
        if test_path.exists():
            spec_path = test_path
        else:
            # Try appending common extensions
            for ext in [".yaml", ".yml"]:
                test_path = DRIVER_SPECS_DIR / f"{spec_file}{ext}"
                if test_path.exists():
                    spec_path = test_path
                    break
    
    if not spec_path.exists():
        click.echo(f"Error: Spec file not found: {spec_file}", err=True)
        ctx.exit(1)
    
    click.echo(f"Loading spec: {spec_path}")
    
    if dry_run:
        click.echo(f"\n[DRY RUN] Would generate charm from: {spec_path}")
        click.echo(f"  Output dir: {output_dir or GENERATED_CHARMS_DIR}")
        click.echo(f"  Model: {model or OPENAI_MODEL}")
        return
    
    generator = CharmGenerator(output_dir=output_dir)
    
    if model:
        from charm_generator.openai_client import CharmGeneratorClient
        generator._api_client = CharmGeneratorClient(model=model)
    
    click.echo(f"Generating charm (model: {model or OPENAI_MODEL})...")
    result = generator.generate(spec_path=spec_path, overwrite=overwrite)
    
    if result.success:
        click.echo(click.style("\n✓ Generation successful!", fg="green"))
        click.echo(f"  Output: {result.output_dir}")
        click.echo(f"  Files: {len(result.files_generated)}")
        click.echo(f"  Duration: {result.duration_seconds:.2f}s")
        click.echo(f"  Tokens: {result.tokens_used}")
        
        # Post-generation instructions
        click.echo(click.style("\n📦 Next steps to pack the charm:", fg="cyan"))
        click.echo(f"  cd {result.output_dir}")
        click.echo("  uv lock        # Generate uv.lock file")
        click.echo("  charmcraft pack")
    else:
        click.echo(click.style(f"\n✗ Generation failed: {result.error_message}", fg="red"), err=True)
        ctx.exit(1)


@cli.command("validate")
@click.argument("vendor")
@click.option("--spec", "-s", type=str, default=None, help="YAML spec file to validate against")
@click.option("--json-output", is_flag=True, default=False)
@click.pass_context
def validate(ctx: click.Context, vendor: str, spec: str | None, json_output: bool) -> None:
    """Validate a generated charm structure.
    
    Use --spec to validate that all config options from the YAML spec
    are correctly present in the generated charm files.
    """
    result = CharmValidator().validate(vendor, spec_path=spec)
    
    if json_output:
        click.echo(json.dumps(result.to_dict(), indent=2))
        ctx.exit(0 if result.valid else 1)
    
    # Show validation mode
    if spec:
        click.echo(f"\nValidating against spec: {spec}")
    
    status = click.style("✓ VALID", fg="green") if result.valid else click.style("✗ INVALID", fg="red")
    click.echo(f"\n{status}: {vendor} ({result.error_count} errors, {result.warning_count} warnings)")
    
    for issue in result.issues:
        color = {"error": "red", "warning": "yellow", "info": "blue"}.get(issue.severity, "white")
        click.echo(click.style(f"  [{issue.severity.upper()}] {issue.message}", fg=color))
    
    ctx.exit(0 if result.valid else 1)


@cli.command("list-specs")
def list_specs() -> None:
    """List available driver specification files."""
    specs = CharmGenerator().list_available_specs()
    click.echo(f"\nAvailable specs ({DRIVER_SPECS_DIR}):\n")
    for spec in specs:
        click.echo(f"  - {spec.name}")
    click.echo(f"\nTotal: {len(specs)} specs")


@cli.command("compare")
@click.argument("vendor1")
@click.argument("vendor2")
@click.option("--json-output", is_flag=True, default=False)
def compare(vendor1: str, vendor2: str, json_output: bool) -> None:
    """Compare two generated charms."""
    result = compare_charms(vendor1, vendor2)
    
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        return
    
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    
    click.echo(f"\n{vendor1}: {result['vendor1_file_count']} files")
    click.echo(f"{vendor2}: {result['vendor2_file_count']} files")
    click.echo(f"Common: {len(result['common_files'])} files")


@cli.command("list-vendors")
def list_vendors() -> None:
    """List all generated vendor charms."""
    writer = CharmFileWriter()
    vendors = writer.list_generated_vendors()
    click.echo(f"\nGenerated charms ({GENERATED_CHARMS_DIR}):\n")
    for vendor in vendors:
        files = writer.get_charm_files(vendor)
        click.echo(f"  - {vendor} ({len(files)} files)")
    click.echo(f"\nTotal: {len(vendors)} vendors")


@cli.command("info")
def info() -> None:
    """Show system configuration."""
    click.echo("\nCharm Generator Configuration:\n")
    for key, value in get_settings_summary().items():
        click.echo(f"  {key}: {value}")
    click.echo(f"\n  specs_dir: {DRIVER_SPECS_DIR}")
    click.echo(f"  output_dir: {GENERATED_CHARMS_DIR}")


@cli.command("clean")
@click.argument("vendor")
@click.option("--yes", "-y", is_flag=True, default=False)
@click.pass_context
def clean(ctx: click.Context, vendor: str, yes: bool) -> None:
    """Delete a generated vendor charm."""
    writer = CharmFileWriter()
    
    if vendor not in writer.list_generated_vendors():
        click.echo(f"Vendor not found: {vendor}", err=True)
        ctx.exit(1)
    
    if not yes:
        click.confirm(f"Delete all files for {vendor}?", abort=True)
    
    if writer.delete_charm(vendor):
        click.echo(f"Deleted: {vendor}")
    else:
        click.echo(f"Failed to delete: {vendor}", err=True)
        ctx.exit(1)


if __name__ == "__main__":
    cli(obj={})
