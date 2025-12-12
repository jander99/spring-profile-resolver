"""Command-line interface for Spring Profile Resolver."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from .env_vars import load_env_file, parse_env_overrides
from .resolver import run_resolver

app = typer.Typer(
    name="spring-profile-resolver",
    help="Compute effective Spring Boot configuration for given profiles.",
    add_completion=False,
)

console = Console()
error_console = Console(stderr=True)


@app.command()
def main(
    project_path: Annotated[
        Path,
        typer.Argument(
            help="Path to Spring Boot project",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ],
    profiles: Annotated[
        str,
        typer.Option(
            "--profiles",
            "-p",
            help="Comma-separated list of profiles to activate",
        ),
    ],
    resources: Annotated[
        str | None,
        typer.Option(
            "--resources",
            "-r",
            help="Comma-separated custom resource directories (relative to project)",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output directory (default: .computed/)",
        ),
    ] = None,
    stdout: Annotated[
        bool,
        typer.Option(
            "--stdout",
            help="Output to stdout instead of file",
        ),
    ] = False,
    include_test: Annotated[
        bool,
        typer.Option(
            "--include-test",
            "-t",
            help="Include test resources (they override main)",
        ),
    ] = False,
    env_file: Annotated[
        Path | None,
        typer.Option(
            "--env-file",
            "-e",
            help="Path to .env file for placeholder resolution",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    env: Annotated[
        list[str] | None,
        typer.Option(
            "--env",
            "-E",
            help="Environment variable override (KEY=value), can be repeated",
        ),
    ] = None,
    no_system_env: Annotated[
        bool,
        typer.Option(
            "--no-system-env",
            help="Don't use system environment variables for placeholder resolution",
        ),
    ] = False,
    vcap_services_file: Annotated[
        Path | None,
        typer.Option(
            "--vcap-services-file",
            help="Path to JSON file containing VCAP_SERVICES (Cloud Foundry)",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    vcap_application_file: Annotated[
        Path | None,
        typer.Option(
            "--vcap-application-file",
            help="Path to JSON file containing VCAP_APPLICATION (Cloud Foundry)",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    ignore_vcap: Annotated[
        bool,
        typer.Option(
            "--ignore-vcap",
            help="Suppress warnings about VCAP_SERVICES/VCAP_APPLICATION not being available",
        ),
    ] = False,
) -> None:
    """Compute effective Spring Boot configuration for given profiles."""
    # Parse profiles
    profile_list = [p.strip() for p in profiles.split(",") if p.strip()]

    if not profile_list:
        error_console.print("[red]Error:[/red] At least one profile must be specified")
        raise typer.Exit(1)

    # Parse resource dirs
    resource_dirs: list[str] | None = None
    if resources:
        resource_dirs = [r.strip() for r in resources.split(",") if r.strip()]

    # Load environment variables
    env_vars: dict[str, str] = {}
    if env_file:
        try:
            env_vars.update(load_env_file(env_file))
        except Exception as e:
            error_console.print(f"[red]Error loading env file:[/red] {e}")
            raise typer.Exit(1) from e

    if env:
        env_vars.update(parse_env_overrides(env))

    # Load VCAP files if provided
    vcap_services_json: str | None = None
    vcap_application_json: str | None = None

    if vcap_services_file:
        try:
            vcap_services_json = vcap_services_file.read_text(encoding="utf-8")
        except Exception as e:
            error_console.print(f"[red]Error loading VCAP_SERVICES file:[/red] {e}")
            raise typer.Exit(1) from e

    if vcap_application_file:
        try:
            vcap_application_json = vcap_application_file.read_text(encoding="utf-8")
        except Exception as e:
            error_console.print(f"[red]Error loading VCAP_APPLICATION file:[/red] {e}")
            raise typer.Exit(1) from e

    try:
        output_yaml, warnings, errors = run_resolver(
            project_path=project_path,
            profiles=profile_list,
            resource_dirs=resource_dirs,
            include_test=include_test,
            output_dir=output,
            to_stdout=stdout,
            env_vars=env_vars if env_vars else None,
            use_system_env=not no_system_env,
            vcap_services_json=vcap_services_json,
            vcap_application_json=vcap_application_json,
            ignore_vcap_warnings=ignore_vcap,
        )

        # Display warnings
        if warnings:
            error_console.print()
            error_console.print(
                Panel(
                    "\n".join(f"[yellow]•[/yellow] {w}" for w in warnings),
                    title="[yellow]Warnings[/yellow]",
                    border_style="yellow",
                )
            )

        # Display errors and fail if any YAML parse errors occurred
        if errors:
            error_console.print()
            error_console.print(
                Panel(
                    "\n".join(f"[red]•[/red] {e}" for e in errors),
                    title="[red]YAML Parse Errors[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

        # Success message (if not stdout mode)
        if not stdout:
            if output:
                output_file = output / f"application-{'-'.join(profile_list)}-computed.yml"
            else:
                output_file = Path.cwd() / ".computed" / f"application-{'-'.join(profile_list)}-computed.yml"

            console.print(
                f"\n[green]✓[/green] Configuration written to [bold]{output_file}[/bold]"
            )

    except typer.Exit:
        raise
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
