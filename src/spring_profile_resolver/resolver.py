"""Main orchestration logic for Spring Profile Resolver."""

from pathlib import Path

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


def resolve_profiles(
    project_path: Path,
    profiles: list[str],
    resource_dirs: list[str] | None = None,
    include_test: bool = False,
    env_vars: dict[str, str] | None = None,
    use_system_env: bool = True,
) -> ResolverResult:
    """Main entry point for profile resolution.

    Steps:
    1. Discover config files in main resources
    2. If include_test=True, also discover test resources
    3. Parse all config documents (YAML and Properties)
    4. Extract and expand profile groups from base config
    5. Filter applicable documents based on active profiles
    6. Merge in order (main first, then test overrides if enabled)
    7. Resolve placeholders (with env var support)
    8. Return result with warnings

    Args:
        project_path: Path to Spring Boot project root
        profiles: List of profile names to activate
        resource_dirs: Optional custom resource directories
        include_test: Whether to include test resources
        env_vars: Optional dict of environment variables for placeholder resolution
        use_system_env: Whether to check system env vars during placeholder resolution

    Returns:
        ResolverResult with merged config, sources, and warnings
    """
    warnings: list[str] = []
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
                    import_docs, import_warnings = _process_imports(
                        documents, base_file, main_dirs, loaded_files
                    )
                    all_documents.extend(import_docs)
                    warnings.extend(import_warnings)
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
                    except Exception as e:
                        warnings.append(f"Error parsing {profile_file}: {e}")

    # Filter documents applicable to active profiles
    applicable_docs = get_applicable_documents(all_documents, expanded_profiles)

    # Sort documents for proper merge order
    sorted_docs = _sort_documents_for_merge(applicable_docs, expanded_profiles, main_dirs, test_dirs)

    # Merge all applicable documents
    merged_config, sources = merge_configs(sorted_docs)

    # Resolve placeholders (with env var support)
    resolved_config, placeholder_warnings = resolve_placeholders(
        merged_config,
        env_vars=env_vars,
        use_system_env=use_system_env,
    )
    warnings.extend(placeholder_warnings)

    return ResolverResult(
        config=resolved_config,
        sources=sources,
        warnings=warnings,
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
) -> tuple[list[ConfigDocument], list[str]]:
    """Process spring.config.import directives from documents.

    Args:
        documents: Documents from the source file
        source_file: Path to the source file
        resource_dirs: Resource directories for classpath: resolution
        loaded_files: Set of already loaded files (modified in place)

    Returns:
        Tuple of (imported_documents, warnings)
    """
    imported_docs: list[ConfigDocument] = []
    warnings: list[str] = []

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
                    nested_docs, nested_warnings = _process_imports(
                        new_docs, import_path, resource_dirs, loaded_files
                    )
                    imported_docs.extend(nested_docs)
                    warnings.extend(nested_warnings)

                except Exception as e:
                    if not optional:
                        warnings.append(f"Error loading imported file {import_path}: {e}")

        except Exception as e:
            warnings.append(f"Error processing imports from {source_file}: {e}")

    return imported_docs, warnings


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
) -> tuple[str, list[str]]:
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

    Returns:
        Tuple of (output_yaml, warnings)
    """
    result = resolve_profiles(
        project_path=project_path,
        profiles=profiles,
        resource_dirs=resource_dirs,
        include_test=include_test,
        env_vars=env_vars,
        use_system_env=use_system_env,
    )

    # Determine output path
    output_path: Path | None = None
    if not to_stdout or output_dir:
        if output_dir is None:
            output_dir = Path.cwd() / ".computed"
        filename = format_output_filename(profiles)
        output_path = output_dir / filename

    # Generate output
    output_yaml = generate_computed_yaml(
        config=result.config,
        sources=result.sources,
        output_path=output_path,
        to_stdout=to_stdout,
    )

    return output_yaml, result.warnings
