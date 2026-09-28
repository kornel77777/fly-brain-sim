"""Run the viewer API (and the built frontend, if web/dist exists).

Usage: uv run python scripts/serve.py [--port 8000] [--reload]
"""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="restart on code changes")
    args = parser.parse_args()
    uvicorn.run("fly_brain_sim.viz.api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
