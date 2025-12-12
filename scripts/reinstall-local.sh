#!/usr/bin/env bash
#
# Reinstall spring-profile-resolver locally after major changes.
# Uninstalls and reinstalls from local source.
#

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Uninstalling existing tool (if any)..."
uv tool uninstall spring-profile-resolver 2>/dev/null || true

echo "==> Installing from local source..."
cd "$PROJECT_ROOT"
uv tool install --force .

echo "==> Verifying installation..."
if spring-profile-resolver --help >/dev/null 2>&1; then
    echo "    spring-profile-resolver is available"
else
    echo "    ERROR: spring-profile-resolver not found in PATH"
    exit 1
fi

echo ""
echo "✓ Done! spring-profile-resolver has been reinstalled from local source."
