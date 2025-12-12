"""Parser for Java .properties files used by Spring Boot.

Supports:
- key=value and key: value syntax
- Multi-line values with \\ continuation
- Comments starting with # or !
- Multi-document separators (#--- or !---)
- Unicode escape sequences (\\uXXXX)
- Conversion of dot-notation keys to nested dicts
"""

import re
from pathlib import Path
from typing import Any

from .models import ConfigDocument

# Pattern for multi-document separator (Spring Boot 2.4+)
DOCUMENT_SEPARATOR_PATTERN = re.compile(r"^[#!]---\s*$")

# Pattern for Spring Boot activation comment
ACTIVATION_PATTERN = re.compile(
    r"^[#!]\s*spring\.config\.activate\.on-profile\s*[=:]\s*(.+)$"
)


def parse_properties_file(path: Path) -> list[ConfigDocument]:
    """Parse a .properties file, handling multi-document format.

    Args:
        path: Path to the .properties file

    Returns:
        List of ConfigDocument objects, one per document in the file

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()

    return parse_properties_content(content, path)


def parse_properties_content(content: str, source_path: Path) -> list[ConfigDocument]:
    """Parse properties content string into ConfigDocument objects.

    Args:
        content: The properties file content
        source_path: Path to attribute as the source

    Returns:
        List of ConfigDocument objects
    """
    documents: list[ConfigDocument] = []
    lines = content.splitlines()

    # Split by document separators
    doc_chunks = _split_into_documents(lines)

    for index, (doc_lines, activation_profile) in enumerate(doc_chunks):
        properties = _parse_properties_lines(doc_lines)

        # Handle activation profile from within the document BEFORE building nested config
        # This ensures the activation key is not included in the final config
        if activation_profile is None:
            activation_profile, properties = _extract_activation_from_properties(properties)

        nested_config = _properties_to_nested_dict(properties)

        if nested_config or activation_profile is not None:
            documents.append(
                ConfigDocument(
                    content=nested_config,
                    source_file=source_path,
                    activation_profile=activation_profile,
                    document_index=index,
                )
            )

    # If no documents were created and file wasn't empty, create one empty document
    if not documents and content.strip():
        documents.append(
            ConfigDocument(
                content={},
                source_file=source_path,
                activation_profile=None,
                document_index=0,
            )
        )

    return documents


def _split_into_documents(
    lines: list[str],
) -> list[tuple[list[str], str | None]]:
    """Split lines into separate documents based on #--- or !--- separators.

    Returns list of (lines, activation_profile) tuples.
    """
    documents: list[tuple[list[str], str | None]] = []
    current_lines: list[str] = []
    current_activation: str | None = None

    for line in lines:
        if DOCUMENT_SEPARATOR_PATTERN.match(line):
            # Save current document if it has content
            if current_lines:
                documents.append((current_lines, current_activation))
            current_lines = []
            current_activation = None
        else:
            # Check for activation profile in comment
            activation_match = ACTIVATION_PATTERN.match(line)
            if activation_match:
                current_activation = activation_match.group(1).strip()
            current_lines.append(line)

    # Don't forget the last document
    if current_lines:
        documents.append((current_lines, current_activation))

    # If no documents, return empty list with one empty document placeholder
    if not documents:
        documents.append(([], None))

    return documents


def _parse_properties_lines(lines: list[str]) -> dict[str, str]:
    """Parse properties lines into a flat key-value dict.

    Handles:
    - key=value syntax
    - key: value syntax
    - key value syntax (space separator)
    - Multi-line continuation with \\
    - Comments starting with # or !
    """
    properties: dict[str, str] = {}
    current_key: str | None = None
    current_value_parts: list[str] = []
    in_continuation = False

    for line in lines:
        # Handle continuation from previous line
        if in_continuation:
            stripped = line.lstrip()
            if stripped.endswith("\\"):
                current_value_parts.append(stripped[:-1])
            else:
                current_value_parts.append(stripped)
                in_continuation = False
                if current_key:
                    properties[current_key] = "".join(current_value_parts)
                current_key = None
                current_value_parts = []
            continue

        # Skip blank lines and comments
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue

        # Parse key-value pair
        key, value = _parse_property_line(stripped)
        if key:
            if value.endswith("\\"):
                # Multi-line value
                current_key = key
                current_value_parts = [value[:-1]]
                in_continuation = True
            else:
                properties[key] = value

    # Handle unterminated continuation
    if current_key and current_value_parts:
        properties[current_key] = "".join(current_value_parts)

    return properties


def _parse_property_line(line: str) -> tuple[str | None, str]:
    """Parse a single property line into key and value.

    Handles:
    - key=value
    - key:value
    - key: value
    - key = value
    """
    # Find the separator (=, :, or first whitespace)
    separator_idx = -1
    separator_char = None

    i = 0
    while i < len(line):
        char = line[i]

        # Handle escape sequences
        if char == "\\":
            i += 2
            continue

        if char in "=:":
            separator_idx = i
            separator_char = char
            break
        elif char.isspace() and separator_char is None:
            # Space can be a separator if no = or : found yet
            separator_idx = i
            separator_char = " "
            break

        i += 1

    if separator_idx == -1:
        # No separator found, treat entire line as key with empty value
        return _unescape_property_string(line.strip()), ""

    key = _unescape_property_string(line[:separator_idx].strip())
    value = line[separator_idx + 1 :].lstrip()

    # Handle the case where separator is followed by = or :
    if separator_char == " " and value and value[0] in "=:":
        value = value[1:].lstrip()

    return key, _unescape_property_string(value)


def _unescape_property_string(s: str) -> str:
    """Unescape a properties file string.

    Handles:
    - \\n, \\t, \\r, \\f
    - \\uXXXX unicode escapes
    - \\\\ for literal backslash
    """
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            next_char = s[i + 1]
            if next_char == "n":
                result.append("\n")
                i += 2
            elif next_char == "t":
                result.append("\t")
                i += 2
            elif next_char == "r":
                result.append("\r")
                i += 2
            elif next_char == "f":
                result.append("\f")
                i += 2
            elif next_char == "\\":
                result.append("\\")
                i += 2
            elif next_char == "u" and i + 5 < len(s):
                # Unicode escape
                try:
                    code_point = int(s[i + 2 : i + 6], 16)
                    # Validate not a surrogate (U+D800-U+DFFF) which are invalid in UTF-8
                    if 0xD800 <= code_point <= 0xDFFF:
                        # Invalid surrogate, treat backslash as literal
                        result.append(s[i])
                        i += 1
                    else:
                        result.append(chr(code_point))
                        i += 6
                except ValueError:
                    result.append(s[i])
                    i += 1
            else:
                # Unknown escape, keep the character after backslash
                result.append(next_char)
                i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _properties_to_nested_dict(properties: dict[str, str]) -> dict[str, Any]:
    """Convert flat dot-notation properties to nested dictionary.

    Example:
        {"server.port": "8080", "server.host": "localhost"}
        ->
        {"server": {"port": "8080", "host": "localhost"}}
    """
    result: dict[str, Any] = {}

    for key, value in properties.items():
        _set_nested_value(result, key, _convert_value(value))

    return result


def _set_nested_value(d: dict[str, Any], key_path: str, value: Any) -> None:
    """Set a value in a nested dict using dot-notation path.

    Handles array notation like server.hosts[0].name
    """
    parts = _parse_key_path(key_path)
    current = d

    for i, part in enumerate(parts[:-1]):
        if isinstance(part, int):
            # This shouldn't happen at root level, skip
            continue

        if part not in current:
            # Look ahead to see if next part is an index
            next_part = parts[i + 1] if i + 1 < len(parts) else None
            if isinstance(next_part, int):
                current[part] = []
            else:
                current[part] = {}

        current = current[part]

        # Handle list access
        if isinstance(current, list) and i + 1 < len(parts):
            next_part = parts[i + 1]
            if isinstance(next_part, int):
                # Extend list if needed
                while len(current) <= next_part:
                    current.append({})
                if i + 2 < len(parts) - 1:
                    current = current[next_part]

    # Set the final value
    final_key = parts[-1]
    if isinstance(final_key, int) and isinstance(current, list):
        while len(current) <= final_key:
            current.append(None)
        current[final_key] = value
    elif isinstance(current, dict):
        current[str(final_key)] = value


def _parse_key_path(key_path: str) -> list[str | int]:
    """Parse a key path into parts, handling array notation.

    Example:
        "server.hosts[0].name" -> ["server", "hosts", 0, "name"]
    """
    parts: list[str | int] = []
    current = ""

    i = 0
    while i < len(key_path):
        char = key_path[i]

        if char == ".":
            if current:
                parts.append(current)
                current = ""
        elif char == "[":
            if current:
                parts.append(current)
                current = ""
            # Find closing bracket
            end = key_path.find("]", i)
            if end != -1:
                try:
                    index = int(key_path[i + 1 : end])
                    parts.append(index)
                except ValueError:
                    current += key_path[i : end + 1]
                i = end
        else:
            current += char

        i += 1

    if current:
        parts.append(current)

    return parts


def _convert_value(value: str) -> Any:
    """Convert a string value to appropriate Python type.

    Handles:
    - Booleans: true, false
    - Integers
    - Floats
    - Null: (empty string stays as empty string)
    """
    # Boolean conversion
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # Integer conversion
    try:
        return int(value)
    except ValueError:
        pass

    # Float conversion
    try:
        return float(value)
    except ValueError:
        pass

    # Return as string
    return value


def _extract_activation_from_properties(
    properties: dict[str, str],
) -> tuple[str | None, dict[str, str]]:
    """Extract spring.config.activate.on-profile from properties.

    Returns the activation profile and a copy of properties with the
    activation key removed (since it's metadata, not config).

    This function does NOT mutate the input properties dict.

    Args:
        properties: Flat properties dictionary

    Returns:
        Tuple of (activation_profile, filtered_properties) where:
        - activation_profile is the value of spring.config.activate.on-profile or None
        - filtered_properties is a copy of properties without the activation key
    """
    key = "spring.config.activate.on-profile"
    if key in properties:
        activation = str(properties[key])
        filtered = {k: v for k, v in properties.items() if k != key}
        return activation, filtered
    return None, properties


def get_profile_from_properties_filename(path: Path) -> str | None:
    """Extract profile name from a properties filename.

    Args:
        path: Path to config file (e.g., application-prod.properties)

    Returns:
        Profile name (e.g., "prod") or None for base application.properties
    """
    stem = path.stem  # e.g., "application-prod"
    if stem == "application":
        return None
    if stem.startswith("application-"):
        return stem[len("application-") :]
    return None
