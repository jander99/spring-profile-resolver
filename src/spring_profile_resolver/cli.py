"""Command-line interface for Spring Profile Resolver."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

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

    try:
        output_yaml, warnings = run_resolver(
            project_path=project_path,
            profiles=profile_list,
            resource_dirs=resource_dirs,
            include_test=include_test,
            output_dir=output,
            to_stdout=stdout,
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
