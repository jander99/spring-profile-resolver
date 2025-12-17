"""Command-line interface for Spring Profile Resolver."""

from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .env_vars import load_env_file, parse_env_overrides
from .output import format_output_filename
from .resolver import run_resolver

console = Console()
error_console = Console(stderr=True)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        pkg_version = version("spring-profile-resolver")
        console.print(f"spring-profile-resolver version {pkg_version}")
        raise typer.Exit()


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
    version_flag: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
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
    validate: Annotated[
        bool,
        typer.Option(
            "--validate",
            help="Enable configuration validation (check for property conflicts)",
        ),
    ] = False,
    security_scan: Annotated[
        bool,
        typer.Option(
            "--security-scan",
            help="Enable security scanning (detect secrets and insecure configurations)",
        ),
    ] = False,
    lint: Annotated[
        bool,
        typer.Option(
            "--lint",
            help="Enable configuration linting (check naming conventions and best practices)",
        ),
    ] = False,
    strict_lint: Annotated[
        bool,
        typer.Option(
            "--strict-lint",
            help="Apply strict linting rules (upgrades warnings to errors)",
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
        except (OSError, ValueError, UnicodeDecodeError) as e:
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
        except (OSError, UnicodeDecodeError) as e:
            error_console.print(f"[red]Error loading VCAP_SERVICES file:[/red] {e}")
            raise typer.Exit(1) from e

    if vcap_application_file:
        try:
            vcap_application_json = vcap_application_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            error_console.print(f"[red]Error loading VCAP_APPLICATION file:[/red] {e}")
            raise typer.Exit(1) from e

    try:
        result = run_resolver(
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
            enable_validation=validate,
            enable_security_scan=security_scan,
            enable_linting=lint,
            strict_linting=strict_lint,
        )

        # Display validation issues
        if result.validation_issues:
            error_console.print()
            lines = []
            for issue in result.validation_issues:
                severity_color = "red" if issue.severity == "error" else "yellow"
                lines.append(f"[{severity_color}]•[/{severity_color}] [{issue.severity.upper()}] {issue.property_path}: {issue.message}")
                if issue.suggestion:
                    lines.append(f"  [dim]→ {issue.suggestion}[/dim]")
            error_console.print(
                Panel(
                    "\n".join(lines),
                    title="[cyan]Validation Issues[/cyan]",
                    border_style="cyan",
                )
            )

        # Display security issues
        if result.security_issues:
            error_console.print()
            lines = []
            for sec_issue in result.security_issues:
                # Map severity to color
                severity_colors = {
                    "critical": "bright_red",
                    "high": "red",
                    "medium": "yellow",
                    "low": "blue",
                }
                color = severity_colors.get(sec_issue.severity, "white")
                lines.append(f"[{color}]•[/{color}] [{sec_issue.severity.upper()}] {sec_issue.property_path}: {sec_issue.message}")
                if sec_issue.recommendation:
                    lines.append(f"  [dim]→ {sec_issue.recommendation}[/dim]")
            error_console.print(
                Panel(
                    "\n".join(lines),
                    title="[red]Security Issues[/red]",
                    border_style="red",
                )
            )

        # Display linting issues
        if result.lint_issues:
            error_console.print()
            lines = []
            for lint_issue in result.lint_issues:
                severity_color = {"error": "red", "warning": "yellow", "info": "blue"}.get(lint_issue.severity, "white")
                lines.append(f"[{severity_color}]•[/{severity_color}] [{lint_issue.severity.upper()}] {lint_issue.property_path}: {lint_issue.message}")
                if lint_issue.suggestion:
                    lines.append(f"  [dim]→ {lint_issue.suggestion}[/dim]")
            error_console.print(
                Panel(
                    "\n".join(lines),
                    title="[magenta]Linting Issues[/magenta]",
                    border_style="magenta",
                )
            )

        # Display warnings
        if result.warnings:
            error_console.print()
            error_console.print(
                Panel(
                    "\n".join(f"[yellow]•[/yellow] {w}" for w in result.warnings),
                    title="[yellow]Warnings[/yellow]",
                    border_style="yellow",
                )
            )

        # Display errors and fail if any YAML parse errors occurred
        if result.errors:
            error_console.print()
            error_console.print(
                Panel(
                    "\n".join(f"[red]•[/red] {e}" for e in result.errors),
                    title="[red]YAML Parse Errors[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

        # Check for critical security issues or validation errors
        has_critical_security = any(i.severity == "critical" for i in result.security_issues)
        has_validation_errors = any(i.severity == "error" for i in result.validation_issues)
        has_lint_errors = any(i.severity == "error" for i in result.lint_issues)

        if has_critical_security or has_validation_errors or has_lint_errors:
            error_console.print()
            error_console.print("[red]Configuration has critical issues that must be addressed.[/red]")
            raise typer.Exit(1)

        # Success message (if not stdout mode)
        if not stdout:
            filename = format_output_filename(profile_list)
            output_dir = output if output else Path.cwd() / ".computed"
            output_file = output_dir / filename

            console.print(
                f"\n[green]✓[/green] Configuration written to [bold]{output_file}[/bold]"
            )

    except (OSError, ValueError, RuntimeError) as e:
        error_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


def app() -> None:
    """Entry point for the CLI application."""
    typer.run(main)


if __name__ == "__main__":
    app()
