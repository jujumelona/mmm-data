"""Command-line read-only inspector; no mutation of source models."""
from __future__ import annotations
import argparse
import json
from .inspect import inspect_file


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inochi2D 0.8 rigging toolkit")
    commands = parser.add_subparsers(dest="cmd", required=True)
    inspect_cmd = commands.add_parser("inspect")
    inspect_cmd.add_argument("model")
    args = parser.parse_args(argv)
    if args.cmd == "inspect":
        print(json.dumps(inspect_file(args.model), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
