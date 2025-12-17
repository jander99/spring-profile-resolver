"""Main orchestration logic for Spring Profile Resolver."""

from pathlib import Path

from .exceptions import InvalidYAMLError
from .imports import load_imports
from .merger import merge_configs
from .models import ConfigDocument, ResolverResult
from .output import format_output_filename, generate_computed_yaml
from .parser import get_profile_from_filename, parse_config_file
from .placeholders import resolve_placeholders
from .profiles import (
    CircularProfileGroupError,
    expand_profiles,
    get_applicable_documents,
    parse_profile_groups,
)

# Maximum depth for spring.config.import recursion (protection against infinite loops)
MAX_IMPORT_DEPTH = 10


def _is_base_config_file(path: Path) -> bool:
    """Check if file is base application config (not profile-specific)."""
    return path.stem == "application"


def _extract_paths_from_dict(
    data: dict, prefix: str, paths: set[str]
) -> None:
    """Recursively extract all dot-notation paths from nested dict."""
    for key, value in data.items():
        current_path = f"{prefix}.{key}" if prefix else key
        paths.add(current_path)

        if isinstance(value, dict):
            _extract_paths_from_dict(value, current_path, paths)


def _collect_base_property_paths(documents: list[ConfigDocument]) -> set[str]:
    """Extract all property paths from base application config files.

    Returns set of dot-notation paths like {"server.port", "spring.application.name"}
    """
    base_paths: set[str] = set()

    for doc in documents:
        if _is_base_config_file(doc.source_file):
            _extract_paths_from_dict(doc.content, "", base_paths)

    return base_paths


def resolve_profiles(
    project_path: Path,
    profiles: list[str],
    resource_dirs: list[str] | None = None,
    include_test: bool = False,
    env_vars: dict[str, str] | None = None,
    use_system_env: bool = True,
    vcap_services_json: str | None = None,
    vcap_application_json: str | None = None,
    ignore_vcap_warnings: bool = False,
    enable_validation: bool = False,
    enable_security_scan: bool = False,
    enable_linting: bool = False,
    strict_linting: bool = False,
) -> ResolverResult:
    """Main entry point for profile resolution.

    Steps:
    1. Discover config files in main resources
    2. If include_test=True, also discover test resources
    3. Parse all config documents (YAML and Properties)
    4. Extract and expand profile groups from base config
    5. Filter applicable documents based on active profiles
    6. Merge in order (main first, then test overrides if enabled)
    7. Resolve placeholders (with env var and VCAP support)
    8. Run validation, security scanning, and linting (if enabled)
    9. Return result with warnings and issues

    Args:
        project_path: Path to Spring Boot project root
        profiles: List of profile names to activate
        resource_dirs: Optional custom resource directories
        include_test: Whether to include test resources
        env_vars: Optional dict of environment variables for placeholder resolution
        use_system_env: Whether to check system env vars during placeholder resolution
        vcap_services_json: Optional VCAP_SERVICES JSON for Cloud Foundry support
        vcap_application_json: Optional VCAP_APPLICATION JSON for Cloud Foundry support
        ignore_vcap_warnings: Whether to suppress VCAP availability warnings
        enable_validation: Whether to run configuration validation
        enable_security_scan: Whether to run security scanning
        enable_linting: Whether to run configuration linting
        strict_linting: Whether to apply strict linting rules

    Returns:
        ResolverResult with merged config, sources, warnings, errors, and analysis results
    """
    warnings: list[str] = []
    errors: list[str] = []
    all_documents: list[ConfigDocument] = []

    # Determine resource directories to scan
    if resource_dirs:
        main_dirs = [project_path / d for d in resource_dirs]
        test_dirs: list[Path] = []  # Custom dirs don't have test/main distinction
    else:
        main_dirs = [project_path / "src" / "main" / "resources"]
        test_dirs = [project_path / "src" / "test" / "resources"] if include_test else []

    # Track loaded files for circular import detection
    loaded_files: set[Path] = set()

    # Step 1: Load ONLY base application config from main resources
    for resource_dir in main_dirs:
        base_files = _find_base_configs(resource_dir)
        if base_files:
            for base_file in base_files:
                try:
                    documents = parse_config_file(base_file)
                    all_documents.extend(documents)
                    loaded_files.add(base_file)

                    # Process imports from this file
                    import_docs, import_warnings, import_errors = _process_imports(
                        documents, base_file, main_dirs, loaded_files
                    )
                    all_documents.extend(import_docs)
                    warnings.extend(import_warnings)
                    errors.extend(import_errors)
                except InvalidYAMLError as e:
                    errors.append(str(e))
                except Exception as e:
                    warnings.append(f"Error parsing {base_file}: {e}")
        elif resource_dir == main_dirs[0]:
            warnings.append(f"No application config found in {resource_dir}")

    # Extract profile groups from base config (first document without activation)
    groups = _extract_profile_groups(all_documents)

    # Expand profiles using groups
    try:
        expanded_profiles = expand_profiles(profiles, groups)
    except CircularProfileGroupError as e:
        warnings.append(str(e))
        expanded_profiles = profiles

    # Step 2: Load profile-specific files ONLY for requested/expanded profiles
    for resource_dir in main_dirs:
        for profile in expanded_profiles:
            profile_files = _find_profile_files(resource_dir, profile)
            for profile_file in profile_files:
                if profile_file not in [d.source_file for d in all_documents]:
                    try:
                        documents = parse_config_file(profile_file)
                        all_documents.extend(documents)
                    except InvalidYAMLError as e:
                        errors.append(str(e))
                    except Exception as e:
                        warnings.append(f"Error parsing {profile_file}: {e}")

    # Step 3: Load test resources (same selective approach)
    for test_dir in test_dirs:
        # Load base test application config
        base_files = _find_base_configs(test_dir)
        for base_file in base_files:
            try:
                documents = parse_config_file(base_file)
                all_documents.extend(documents)
            except InvalidYAMLError as e:
                errors.append(str(e))
            except Exception as e:
                warnings.append(f"Error parsing {base_file}: {e}")

        # Load profile-specific test files
        for profile in expanded_profiles:
            profile_files = _find_profile_files(test_dir, profile)
            for profile_file in profile_files:
                if profile_file not in [d.source_file for d in all_documents]:
                    try:
                        documents = parse_config_file(profile_file)
                        all_documents.extend(documents)
                    except InvalidYAMLError as e:
                        errors.append(str(e))
                    except Exception as e:
                        warnings.append(f"Error parsing {profile_file}: {e}")

    # Filter documents applicable to active profiles
    applicable_docs = get_applicable_documents(all_documents, expanded_profiles)

    # Sort documents for proper merge order
    sorted_docs = _sort_documents_for_merge(applicable_docs, expanded_profiles, main_dirs, test_dirs)

    # Merge all applicable documents
    merged_config, sources = merge_configs(sorted_docs)

    # Collect base property paths for comment/warning logic
    base_properties = _collect_base_property_paths(all_documents)

    # Resolve placeholders (with env var and VCAP support)
    resolved_config, placeholder_warnings = resolve_placeholders(
        merged_config,
        env_vars=env_vars,
        use_system_env=use_system_env,
        vcap_services_json=vcap_services_json,
        vcap_application_json=vcap_application_json,
        ignore_vcap_warnings=ignore_vcap_warnings,
    )
    warnings.extend(placeholder_warnings)

    # Run validation, security scanning, and linting if enabled
    from .linting import LintIssue, lint_configuration
    from .security import SecurityIssue, scan_configuration
    from .validation import ValidationIssue, validate_configuration

    validation_issues: list[ValidationIssue] = []
    security_issues: list[SecurityIssue] = []
    lint_issues: list[LintIssue] = []

    if enable_validation:
        validation_issues = validate_configuration(resolved_config)

    if enable_security_scan:
        security_issues = scan_configuration(resolved_config)

    if enable_linting:
        lint_issues = lint_configuration(resolved_config, strict=strict_linting)

    return ResolverResult(
        config=resolved_config,
        sources=sources,
        base_properties=base_properties,
        warnings=warnings,
        errors=errors,
        validation_issues=validation_issues,
        security_issues=security_issues,
        lint_issues=lint_issues,
    )


def _extract_profile_groups(documents: list[ConfigDocument]) -> dict[str, list[str]]:
    """Extract profile group definitions from documents.

    Looks in base config documents (those without activation conditions)
    for spring.profiles.group.* definitions.
    """
    groups: dict[str, list[str]] = {}

    for doc in documents:
        if doc.activation_profile is None:
            doc_groups = parse_profile_groups(doc.content)
            groups.update(doc_groups)

    return groups


def _process_imports(
    documents: list[ConfigDocument],
    source_file: Path,
    resource_dirs: list[Path],
    loaded_files: set[Path],
    max_depth: int = MAX_IMPORT_DEPTH,
    current_depth: int = 0,
) -> tuple[list[ConfigDocument], list[str], list[str]]:
    """Process spring.config.import directives from documents.

    Args:
        documents: Documents from the source file
        source_file: Path to the source file
        resource_dirs: Resource directories for classpath: resolution
        loaded_files: Set of already loaded files (modified in place)
        max_depth: Maximum import recursion depth (default: 10)
        current_depth: Current recursion depth (internal)

    Returns:
        Tuple of (imported_documents, warnings, errors)
    """
    imported_docs: list[ConfigDocument] = []
    warnings: list[str] = []
    errors: list[str] = []

    # Check depth limit to prevent infinite recursion
    if current_depth >= max_depth:
        warnings.append(
            f"Import depth limit ({max_depth}) exceeded at {source_file}. "
            f"This may indicate circular imports or overly nested configuration."
        )
        return imported_docs, warnings, errors

    for doc in documents:
        if doc.activation_profile is not None:
            # Don't process imports from profile-specific sections
            continue

        try:
            import_paths = load_imports(
                doc.content, source_file, resource_dirs, loaded_files.copy()
            )

            for import_path, optional in import_paths:
                if import_path in loaded_files:
                    continue  # Already loaded

                if not import_path.exists():
                    if not optional:
                        warnings.append(f"Imported file not found: {import_path}")
                    continue

                try:
                    loaded_files.add(import_path)
                    new_docs = parse_config_file(import_path)
                    imported_docs.extend(new_docs)

                    # Recursively process imports from this file
                    nested_docs, nested_warnings, nested_errors = _process_imports(
                        new_docs, import_path, resource_dirs, loaded_files,
                        max_depth=max_depth, current_depth=current_depth + 1
                    )
                    imported_docs.extend(nested_docs)
                    warnings.extend(nested_warnings)
                    errors.extend(nested_errors)

                except InvalidYAMLError as e:
                    errors.append(str(e))
                except Exception as e:
                    if not optional:
                        warnings.append(f"Error loading imported file {import_path}: {e}")

        except Exception as e:
            warnings.append(f"Error processing imports from {source_file}: {e}")

    return imported_docs, warnings, errors


def _find_base_configs(resource_dir: Path) -> list[Path]:
    """Find base application config files (YAML and Properties).

    Returns files in order: .yml, .yaml, .properties
    (later files have higher precedence in merge order)
    """
    files = []
    for ext in [".yml", ".yaml", ".properties"]:
        base_file = resource_dir / f"application{ext}"
        if base_file.exists():
            files.append(base_file)
    return files


def _find_profile_files(resource_dir: Path, profile: str) -> list[Path]:
    """Find profile-specific config files (YAML and Properties).

    Returns files in order: .yml, .yaml, .properties
    (later files have higher precedence in merge order)
    """
    files = []
    for ext in [".yml", ".yaml", ".properties"]:
        profile_file = resource_dir / f"application-{profile}{ext}"
        if profile_file.exists():
            files.append(profile_file)
    return files


def _sort_documents_for_merge(
    documents: list[ConfigDocument],
    profiles: list[str],
    main_dirs: list[Path],
    test_dirs: list[Path],
) -> list[ConfigDocument]:
    """Sort documents for proper merge order.

    Order:
    1. Base application.yml from main (no activation)
    2. Activated sections from base application.yml
    3. Base application.properties from main (higher precedence than YAML)
    4. Profile-specific files in profile order (.yml then .properties)
    5. Test resources (same ordering as main)
    """

    def sort_key(doc: ConfigDocument) -> tuple[int, int, int, int, int]:
        # Determine if main or test resource
        is_test = any(
            str(doc.source_file).startswith(str(test_dir))
            for test_dir in test_dirs
        )
        location_order = 1 if is_test else 0

        # Get profile from filename
        file_profile = get_profile_from_filename(doc.source_file)

        # Extension order: .properties has higher precedence (comes later)
        suffix = doc.source_file.suffix.lower()
        extension_order = 1 if suffix == ".properties" else 0

        if file_profile is None:
            # Base application config
            file_order = 0
            profile_order = 0
        else:
            # Profile-specific file
            file_order = 1
            try:
                profile_order = profiles.index(file_profile)
            except ValueError:
                profile_order = 999

        # Documents within same file maintain their order
        doc_order = doc.document_index

        return (location_order, file_order, profile_order, extension_order, doc_order)

    return sorted(documents, key=sort_key)


def run_resolver(
    project_path: Path,
    profiles: list[str],
    resource_dirs: list[str] | None = None,
    include_test: bool = False,
    output_dir: Path | None = None,
    to_stdout: bool = False,
    env_vars: dict[str, str] | None = None,
    use_system_env: bool = True,
    vcap_services_json: str | None = None,
    vcap_application_json: str | None = None,
    ignore_vcap_warnings: bool = False,
    enable_validation: bool = False,
    enable_security_scan: bool = False,
    enable_linting: bool = False,
    strict_linting: bool = False,
) -> ResolverResult:
    """Run the full resolver pipeline and generate output.

    Args:
        project_path: Path to Spring Boot project
        profiles: List of profiles to activate
        resource_dirs: Optional custom resource directories
        include_test: Whether to include test resources
        output_dir: Output directory (defaults to .computed/)
        to_stdout: Whether to print to stdout
        env_vars: Optional dict of environment variables for placeholder resolution
        use_system_env: Whether to check system env vars during placeholder resolution
        vcap_services_json: Optional VCAP_SERVICES JSON for Cloud Foundry support
        vcap_application_json: Optional VCAP_APPLICATION JSON for Cloud Foundry support
        ignore_vcap_warnings: Whether to suppress VCAP availability warnings
        enable_validation: Whether to run configuration validation
        enable_security_scan: Whether to run security scanning
        enable_linting: Whether to run configuration linting
        strict_linting: Whether to apply strict linting rules

    Returns:
        ResolverResult with all configuration and analysis results
    """
    result = resolve_profiles(
        project_path=project_path,
        profiles=profiles,
        resource_dirs=resource_dirs,
        include_test=include_test,
        env_vars=env_vars,
        use_system_env=use_system_env,
        vcap_services_json=vcap_services_json,
        vcap_application_json=vcap_application_json,
        ignore_vcap_warnings=ignore_vcap_warnings,
        enable_validation=enable_validation,
        enable_security_scan=enable_security_scan,
        enable_linting=enable_linting,
        strict_linting=strict_linting,
    )

    # Determine output path
    output_path: Path | None = None
    if not to_stdout or output_dir:
        if output_dir is None:
            output_dir = Path.cwd() / ".computed"
        filename = format_output_filename(profiles)
        output_path = output_dir / filename

    # Generate output
    output_yaml, validation_error, new_property_warnings = generate_computed_yaml(
        config=result.config,
        sources=result.sources,
        base_properties=result.base_properties,
        output_path=output_path,
        to_stdout=to_stdout,
    )

    # Collect errors
    errors = result.errors.copy()
    if validation_error:
        errors.append(validation_error)

    # Add new property warnings from output generation
    all_warnings = result.warnings + new_property_warnings

    # Update result with combined warnings and errors
    result.warnings = all_warnings
    result.errors = errors

    return result
