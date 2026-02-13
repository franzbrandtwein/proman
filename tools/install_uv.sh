#!/bin/bash
set -e

echo "Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh

echo ""
echo "uv installation complete!"
echo "You may need to restart your shell or run: source ~/.bashrc"
