"""Run the local workspace with Waitress, without Flask's development debugger."""
import argparse
from generative_app import create_app
from waitress import serve


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generativity project workspace")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    app = create_app()
    print(f"Generativity workspace: http://{args.host}:{args.port}", flush=True)
    serve(app, host=args.host, port=args.port, threads=8)
