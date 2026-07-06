"""Command-line entry point (contracts/cli.md, FR-007)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import load_config
from app.runner import RunManager, RunRejected

RUNS_ROOT_DEFAULT = Path("app/runs")
SAMPLES_ROOT_DEFAULT = Path("app/samples")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Browser Automation Agent CLI"
    )
    parser.add_argument("--goal", help="Natural-language goal for a custom run")
    parser.add_argument("--start-url", help="Starting URL for a custom run")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if not args.goal or not args.start_url:
        print("Error: --goal and --start-url are required", file=sys.stderr)
        return 2

    config = load_config()
    manager = RunManager(
        config=config, runs_root=RUNS_ROOT_DEFAULT, samples_root=SAMPLES_ROOT_DEFAULT
    )

    try:
        run = manager.trigger_run(args.goal, args.start_url)
    except RunRejected as exc:
        print(f"Run rejected: {exc}", file=sys.stderr)
        return 1

    print(f"Run {run.run_id}: {run.status}")
    if run.result_summary:
        print(run.result_summary)
    return 0 if run.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
