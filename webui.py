from dotenv import load_dotenv
load_dotenv()
import argparse
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from src.webui.interface import theme_map, create_ui


class ReportHandler(SimpleHTTPRequestHandler):
    """Custom handler to serve Playwright reports"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="./tmp/test_results", **kwargs)
    
    def do_GET(self):
        if self.path.startswith('/reports/'):
            # Remove /reports/ prefix and serve from test_results directory
            self.path = self.path[9:]  # Remove '/reports/' prefix
            return super().do_GET()
        else:
            self.send_error(404, "Not found")


def start_report_server(port=7789):
    """Start a simple HTTP server for serving Playwright reports"""
    server = HTTPServer(('0.0.0.0', port), ReportHandler)
    print(f"Starting report server on http://0.0.0.0:{port}")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Gradio WebUI for Browser Agent")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=7788, help="Port to listen on")
    parser.add_argument("--theme", type=str, default="Ocean", choices=theme_map.keys(), help="Theme to use for the UI")
    args = parser.parse_args()

    # Start report server in background thread
    report_thread = threading.Thread(target=start_report_server, args=(7789,), daemon=True)
    report_thread.start()

    demo = create_ui(theme_name=args.theme)
    demo.queue().launch(server_name=args.ip, server_port=args.port)


if __name__ == '__main__':
    main()
