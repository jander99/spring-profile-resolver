"""Custom exceptions for Spring Profile Resolver."""

from pathlib import Path


class SpringProfileResolverError(Exception):
    """Base exception for Spring Profile Resolver."""

    pass


class ConfigFileError(SpringProfileResolverError):
    """Error related to configuration file parsing or loading."""

    def __init__(self, file_path: Path, message: str) -> None:
        self.file_path = file_path
        self.message = message
        super().__init__(f"{file_path}: {message}")


class InvalidYAMLError(ConfigFileError):
    """Error when YAML file is malformed."""

    def __init__(self, file_path: Path, line: int | None = None, details: str = "") -> None:
        self.line = line
        location = f" at line {line}" if line else ""
        msg = f"Invalid YAML syntax{location}"
        if details:
            msg += f": {details}"
        super().__init__(file_path, msg)


class ProfileResolutionError(SpringProfileResolverError):
    """Error during profile resolution."""

    pass


class ProfileExpressionError(ProfileResolutionError):
    """Raised when a profile expression is invalid."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Invalid profile expression: {message}")


class CircularProfileGroupError(ProfileResolutionError):
    """Raised when circular profile group references are detected."""

    def __init__(self, cycle_path: list[str]) -> None:
        self.cycle_path = cycle_path
        cycle_str = " -> ".join(cycle_path)
        super().__init__(f"Circular profile group reference detected: {cycle_str}")


class NoConfigurationFoundError(SpringProfileResolverError):
    """Raised when no configuration files are found."""

    def __init__(self, search_paths: list[Path]) -> None:
        self.search_paths = search_paths
        paths_str = ", ".join(str(p) for p in search_paths)
        super().__init__(f"No application.yml found in: {paths_str}")
