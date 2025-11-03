#!/usr/bin/env python3
import sys
import socket
import argparse
import markdown
import webbrowser
import threading
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from watchfiles import watch
from pygments.formatters import HtmlFormatter

# Generate Pygments CSS for syntax highlighting (GitHub style)
PYGMENTS_CSS = HtmlFormatter(style='github-dark').get_style_defs('.codehilite')

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
    /* Pygments syntax highlighting */
    """ + PYGMENTS_CSS + """
</style>
"""

AUTO_RELOAD_SCRIPT = """
<script>
const eventSource = new EventSource('/events');
eventSource.onmessage = (event) => {
    if (event.data === 'reload') {
        location.reload();
    }
};
eventSource.onerror = () => {
    console.log('SSE connection error, will retry...');
};
</script>
"""


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads"""

    daemon_threads = True


class ContentCache:
    """Stores generated HTML and provides regeneration hook"""

    def __init__(self, md_file):
        self.md_file = md_file
        self.html = self.generate()
        self.reload_event = threading.Event()

    def generate(self):
        """Generate HTML from the markdown file"""
        md_text = read_markdown_file(self.md_file)
        html_content = convert_markdown(md_text)
        return build_html_page(html_content, self.md_file.name)

    def refresh(self):
        """Regenerate HTML from file (call when file changes)"""
        self.html = self.generate()
        # Signal all waiting SSE connections
        self.reload_event.set()
        self.reload_event.clear()

    def get(self):
        """Get current cached HTML"""
        return self.html

    def wait_for_reload(self, timeout=30):
        """Wait for a reload event (for SSE clients)"""
        return self.reload_event.wait(timeout)


class MarkdownHandler(BaseHTTPRequestHandler):
    content_cache: ContentCache | None = None

    def do_GET(self):
        if self.path == "/events":
            self.handle_sse()
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = self.content_cache.get() if self.content_cache else ""
            self.wfile.write(html.encode("utf-8"))

    def handle_sse(self):
        """Handle Server-Sent Events connection"""
        if not self.content_cache:
            self.send_error(503, "Service not ready")
            return

        self.send_response(200)
        self.send_header("Content-type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            while True:
                # Wait for reload signal (with timeout to keep connection alive)
                if self.content_cache.wait_for_reload(timeout=30):
                    message = "data: reload\n\n"
                    self.wfile.write(message.encode("utf-8"))
                    self.wfile.flush()
                else:
                    # Timeout - send keepalive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            # Client disconnected
            pass

    def handle(self):
        """Override handle to suppress connection errors from SSE disconnects"""
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            # These errors are expected when SSE clients disconnect
            pass

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def find_available_port(start_port=6914, max_attempts=100):
    """Find an available port starting from start_port"""
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


def read_markdown_file(file_path):
    """Read markdown file with error handling"""
    if not file_path.exists():
        raise FileNotFoundError(f"File '{file_path}' not found")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise IOError(f"Error reading file: {e}") from e


def convert_markdown(md_text):
    """Convert markdown text to HTML with fallback for missing extensions"""
    try:
        return markdown.markdown(
            md_text, extensions=["extra", "codehilite", "tables", "fenced_code"]
        )
    except Exception:
        return markdown.markdown(md_text)


def build_html_page(content, title):
    """Build complete HTML page with GitHub styling"""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    {GITHUB_CSS}
    {AUTO_RELOAD_SCRIPT}
</head>
<body>
    <div class="markdown-body">
        {content}
    </div>
</body>
</html>
"""


def watch_and_refresh(cache, md_file):
    """Watch markdown file for changes and refresh cache"""
    for changes in watch(md_file):
        try:
            cache.refresh()
            print(f"Refreshed: {md_file.name}")
        except Exception as e:
            print(f"Error refreshing: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Render Markdown files in browser with GitHub styling"
    )
    parser.add_argument("file", type=Path, help="Markdown file to render")
    args = parser.parse_args()

    md_file = args.file

    try:
        cache = ContentCache(md_file)
    except (FileNotFoundError, IOError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    MarkdownHandler.content_cache = cache

    try:
        port = find_available_port(6914)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Start server
    try:
        server = ThreadingHTTPServer(("localhost", port), MarkdownHandler)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

    print(f"Serving '{md_file.name}' at http://localhost:{port}")
    print("Watching for changes...")
    print("Press Ctrl+C to stop the server")

    watcher_thread = threading.Thread(
        target=watch_and_refresh, args=(cache, md_file), daemon=True
    )
    watcher_thread.start()

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
