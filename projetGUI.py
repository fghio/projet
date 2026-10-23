"""
ProJet GUI: interactive engine-cycle analysis in the browser.

Usage:
    python3 projetGUI.py [--port 8050] [--no-browser]
"""
import argparse
import threading
import webbrowser

from gui.server import app, local_plotly_js


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ProJet graphical interface")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"ProJet GUI running at {url}  (Ctrl+C to stop)")
    if local_plotly_js() is None:
        print("Warning: the 'plotly' package is not installed for this Python interpreter;\n"
              "         charts are loaded from the internet. For offline use: pip install plotly")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    app.run(host=args.host, port=args.port, debug=False)
