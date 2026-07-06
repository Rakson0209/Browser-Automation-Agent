"""Command-line entry point (contracts/cli.md, FR-007)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import load_config
from app.runner import RunManager, RunRejected
from app.tasks import PRESETS, get_preset

RUNS_ROOT_DEFAULT = Path("app/runs")
SAMPLES_ROOT_DEFAULT = Path("app/samples")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Browser Automation Agent CLI"
    )
    parser.add_argument("--goal", help="Natural-language goal for a custom run")
    parser.add_argument("--start-url", help="Starting URL for a custom run")
    parser.add_argument("--preset", help="Run a preset task by key instead of a custom goal")
    parser.add_argument(
        "--list-presets", action="store_true", help="List available preset tasks and exit"
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_presets:
        for preset in PRESETS:
            print(f"{preset.key}\t{preset.label}\t{preset.start_url}")
        return 0

    if args.preset:
        preset = get_preset(args.preset)
        if preset is None:
            print(f"Error: unknown preset {args.preset!r}", file=sys.stderr)
            return 2
        goal, start_url = preset.goal, preset.start_url
    elif args.goal and args.start_url:
        goal, start_url = args.goal, args.start_url
    else:
        print(
            "Error: provide --preset <key>, or both --goal and --start-url, "
            "or --list-presets",
            file=sys.stderr,
        )
        return 2

    config = load_config()
    manager = RunManager(
        config=config, runs_root=RUNS_ROOT_DEFAULT, samples_root=SAMPLES_ROOT_DEFAULT
    )

    try:
        run = manager.trigger_run(goal, start_url)
    except RunRejected as exc:
        print(f"Run rejected: {exc}", file=sys.stderr)
        return 1

    print(f"Run {run.run_id}: {run.status}")
    if run.result_summary:
        print(run.result_summary)
    return 0 if run.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
