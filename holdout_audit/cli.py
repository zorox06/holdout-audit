"""CLI, demo fixtures, and atomic report writes."""

from __future__ import annotations

import argparse
from importlib.resources import as_file, files
import os
from pathlib import Path
import sys
import tempfile

from .core import AuditError, Report, audit
from .render import render_html, render_json


def _write(path: Path, content: str) -> None:
    """Replace a report atomically without leaving a partially written file."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _print_report(report: Report) -> None:
    print("\nSPLIV | evidence-first split checks\n")
    markers = {"flag": "[!]", "pass": "[+]", "inconclusive": "[?]", "skipped": "[-]"}
    for check in report.checks:
        print(f"{markers[check.status]} {check.title}: {check.summary}")
    print(f"\nVerdict: {report.verdict.replace('_', ' ')}")
    print("Exact matches are review signals; this is not a leakage-free certificate.\n")


def _outputs(parser: argparse.ArgumentParser, args: argparse.Namespace) -> list[Path]:
    paths = [Path(args.output)] if args.output else []
    if args.json:
        paths.append(Path(args.json))
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        parser.error("HTML and JSON outputs must have different paths")
    inputs = {Path(args.train).resolve(), Path(args.test).resolve()} if args.command == "audit" else set()
    for path, canonical in zip(paths, resolved):
        # samefile also catches output symlinks and hardlinks pointing to an input.
        linked_to_input = args.command == "audit" and path.exists() and any(
            Path(source).exists() and path.samefile(source) for source in (args.train, args.test)
        )
        if canonical in inputs or linked_to_input:
            parser.error("An output cannot overwrite an input CSV")
    if len(paths) == 2 and all(path.exists() for path in paths) and paths[0].samefile(paths[1]):
        parser.error("HTML and JSON outputs must not refer to the same file")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit CSV train/test splits locally. No dependencies or API keys.")
    parser.add_argument("--version", action="version", version="spliv 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("audit", help="Audit your train and test CSVs")
    inspect.add_argument("train")
    inspect.add_argument("test")
    inspect.add_argument("--target", help="Target column; excluded from feature comparisons")
    inspect.add_argument("--group", help="Entity ID column; check for shared entities")
    inspect.add_argument("--time", help="ISO 8601 column; check strict future holdout")
    inspect.add_argument("--ignore", action="append", default=[], metavar="COLUMN", help="Exclude a feature; repeat for multiple columns")
    demo = commands.add_parser("demo", help="Try the bundled synthetic split")
    demo.add_argument("--clean", action="store_true", help="Use the repaired synthetic split")
    for command in (inspect, demo):
        command.add_argument("--output", default="report.html", metavar="HTML", help="HTML report path (default: report.html)")
        command.add_argument("--json", metavar="JSON", help="Also export machine-readable evidence")
        command.add_argument("--fail-on", choices=("none", "warning", "error"), default="none" if command is demo else "warning", help="Exit 1 on findings at this level, or incomplete requested checks")
    args = parser.parse_args(argv)
    try:
        _outputs(parser, args)
        if args.command == "demo":
            suffix = "clean" if args.clean else "leaky"
            # Filesystem installs need no scratch directory; zip resources use temporary files.
            data = files("holdout_audit").joinpath("data")
            with as_file(data.joinpath(f"train-{suffix}.csv")) as train, as_file(data.joinpath(f"test-{suffix}.csv")) as test:
                report = audit(train, test, target="churn", group="customer_id", time="observed_at", ignore=("record_id",))
        else:
            report = audit(args.train, args.test, target=args.target, group=args.group, time=args.time, ignore=tuple(args.ignore))
        if args.output:
            _write(Path(args.output), render_html(report))
        if args.json:
            _write(Path(args.json), render_json(report))
        _print_report(report)
        if args.output:
            print(f"HTML: {args.output}")
        if args.json:
            print(f"JSON: {args.json}")
        return int(report.fails(args.fail_on))
    except (AuditError, OSError) as error:
        if isinstance(error, AuditError):
            print(f"spliv: {error}", file=sys.stderr)
        else:
            print("spliv: input or report file could not be accessed; check paths and permissions", file=sys.stderr)
        return 2
