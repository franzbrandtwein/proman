#!/bin/bash
set -e

echo "Running proman from git@github.com:franzbrandtwein/proman.git with uvx..."
uvx --from git+ssh://git@github.com/franzbrandtwein/proman.git proman "$@"
