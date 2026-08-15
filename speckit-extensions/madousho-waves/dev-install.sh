#!/usr/bin/env bash
# Push the working copy of this extension into a project that has it installed.
#
#     ./dev-install.sh /path/to/your/project
#
# Re-runs the Spec Kit dev install, which re-copies the extension and re-renders
# the command files. Run state under .specify/waves/ is untouched.
#
# This script is development-only; .extensionignore keeps it out of installs.

set -euo pipefail

extension_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="${1:-}"

if [[ -z "$project" ]]; then
    echo "usage: $(basename "$0") <project-root>" >&2
    exit 1
fi

if [[ ! -d "$project/.specify" ]]; then
    echo "error: $project has no .specify/ — not a Spec Kit project" >&2
    exit 1
fi

python3 "$extension_dir/tests/test_waves.py" >/dev/null
echo "tests ok"

cd "$project"
specify extension add --dev "$extension_dir" --force
