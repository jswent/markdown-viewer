#!/usr/bin/env python3
import sys
import socket
import markdown
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Link to GitHub's official markdown CSS from CDN
GITHUB_CSS = """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown.min.css">
<style>
    html {
        color-scheme: light dark;
    }
    .markdown-body {
        box-sizing: border-box;
        min-width: 200px;
        max-width: 980px;
        margin: 0 auto;
        padding: 45px;
    }
</style>
"""


class MarkdownHandler(BaseHTTPRequestHandler):
    markdown_content = ""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.markdown_content.encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def find_available_port(start_port=6914, max_attempts=100):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"Could not find an available port in range {start_port}-{start_port + max_attempts}"
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python md_viewer.py <markdown_file.md>")
        sys.exit(1)

    md_file = Path(sys.argv[1])

    if not md_file.exists():
        print(f"Error: File '{md_file}' not found")
        sys.exit(1)

    # Read and convert markdown to HTML
    try:
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    # Convert markdown with available extensions
    try:
        html_content = markdown.markdown(
            md_text, extensions=["extra", "codehilite", "tables", "fenced_code"]
        )
    except Exception:
        # Fallback to basic markdown if extensions fail
        html_content = markdown.markdown(md_text)

    # Create full HTML page with GitHub styling
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{md_file.name}</title>
    {GITHUB_CSS}
</head>
<body>
    <div class="markdown-body">
        {html_content}
    </div>
</body>
</html>
"""

    # Set the content for the handler
    MarkdownHandler.markdown_content = full_html

    # Find available port
    try:
        port = find_available_port(6914)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Start server
    try:
        server = HTTPServer(("localhost", port), MarkdownHandler)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

    print(f"Serving '{md_file.name}' at http://localhost:{port}")
    print("Press Ctrl+C to stop the server")

    # Open browser
    webbrowser.open(f"http://localhost:{port}")

    # Keep server running
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
