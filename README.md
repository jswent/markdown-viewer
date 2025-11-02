# Markdown Viewer

A simple command-line tool to view Markdown files in your browser with GitHub styling.

## Installation

```bash
# Install the package
make install

# Optional: Create a global command
make link
```

The `make link` command creates a wrapper script in `~/.local/bin/mdview` (make sure this directory is in your PATH).

## Requirements

- Python >= 3.7
- `markdown` library (installed automatically)

## Uninstalling

```bash
# Remove the global command
make unlink

# Clean up virtual environment and build artifacts
make clean
```
