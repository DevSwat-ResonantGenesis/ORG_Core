#!/bin/bash
# Install CASCADE git hooks

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"

if [ -z "$GIT_DIR" ]; then
    echo "Error: Not a git repository"
    exit 1
fi

# Install pre-commit hook
cp "$SCRIPT_DIR/pre-commit" "$GIT_DIR/hooks/pre-commit"
chmod +x "$GIT_DIR/hooks/pre-commit"

echo "CASCADE pre-commit hook installed successfully"
echo "All commits will now require impact analysis"
