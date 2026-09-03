"""`fmb` — run the benchmark, browse results, publish one."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from bench import BENCH_VERSION, RELEASE_SEED
from bench.runner import GOVERNANCE_FAMILIES, run as run_bench
from bench.schema import validate

RUNS_DIR = Path(os.environ.get("FMB_HOME", Path.home() / ".fmb")) / "runs"
REPO_RESULTS = Path(__file__).resolve().parent.parent / "results"


# --- loading a system -----------------------------------------------------

def load_system(spec: str):
    """`http://host:port` for the canonical binding, or `module:Class` for a
    Python adapter. `null` is the built-in baseline."""
    if spec == "null":
        from bench.adapter.null import NullMemory

        return NullMemory()
    if spec.startswith("http://") or spec.startswith("https://"):
        from bench.adapter.http import HttpSystem

        return HttpSystem(spec)
    if ":" not in spec:
        raise SystemExit(
            f"cannot load system {spec!r}: expected a URL, `module:Class`, or `null`"
        )
    module_name, _, attr = spec.partition(":")
    module = importlib.import_module(module_name)
    factory = getattr(module, attr)
    return factory()


# --- commands -------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    system = load_system(args.system)
    families = sorted(set(args.families.split(","))) if args.families else None

    total = 0

    def progress(result, attempt):
        nonlocal total
        total += 1
        if args.verbose:
            mark = "skip" if result.skipped else ("PASS" if result.passed else "FAIL")
            print(f"  {mark:4}  {result.id}", file=sys.stderr)
        elif total % 20 == 0:
            print(".", end="", file=sys.stderr, flush=True)

    result = run_bench(
        system, families=families, seed=args.seed, repeat=args.repeat, progress=progress
    )
    if not args.verbose:
        print(file=sys.stderr)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{result.run_id}.json"
    path.write_text(json.dumps(result.to_json(), indent=2) + "\n")

    print_summary(result.to_json())
    print(f"\nrun file: {path}")
    if not result.submittable:
        print("this run is NOT submittable: " + "; ".join(result.notes))
    return 0


def print_summary(run: dict) -> None:
    h = run["headline"]
    print(f"\n{run['system']['name']}  ({run['system']['version']})")
    print(f"  governance   {h['governance']:.3f}   (weakest of {', '.join(GOVERNANCE_FAMILIES)})")
    print(f"  contribution {h['contribution']:.3f}")
    print()
    for fam, block in run["families"].items():
        spread = block.get("spread")
        extra = f"  spread {spread['min']:.2f}–{spread['max']:.2f}" if spread else ""
        flag = f"  unsupported:{block['unsupported']}" if block["unsupported"] else ""
        print(
            f"  {fam}  {block['rate']:.3f}  ({block['pass']}/{block['total']}"
            f", wilson≥{block['wilson_low']:.2f}){flag}{extra}"
        )
    p = run["policy"]
    if p["total"]:
        print(f"  P  {p['rate']:.3f}  ({p['pass']}/{p['total']})  policy conformance, not scored")


def cmd_validate(args: argparse.Namespace) -> int:
    problems: list[str] = []
    for path in args.paths:
        run = json.loads(Path(path).read_text())
        found = validate(run, for_submission=args.submission)
        for problem in found:
            print(f"{path}: {problem}", file=sys.stderr)
        problems.extend(found)
    if problems:
        print(f"{len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(f"{len(args.paths)} run file(s) valid")
    return 0


def _load_runs() -> list[dict]:
    runs: list[dict] = []
    for path in sorted(REPO_RESULTS.glob("*/*.json")) if REPO_RESULTS.exists() else []:
        run = json.loads(path.read_text())
        run["_published"] = True
        runs.append(run)
    for path in sorted(RUNS_DIR.glob("*.json")) if RUNS_DIR.exists() else []:
        run = json.loads(path.read_text())
        if any(r["run_id"] == run["run_id"] for r in runs):
            continue
        run["_published"] = False
        runs.append(run)
    return runs


def cmd_ui(args: argparse.Namespace) -> int:
    from bench.ui import build_site

    out = Path(args.out)
    build_site(_load_runs(), out)
    index = out / "index.html"
    print(f"site: {index}")
    if not args.no_open:
        webbrowser.open(index.as_uri())
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    path = RUNS_DIR / f"{args.run_id}.json"
    if not path.exists():
        candidates = list(RUNS_DIR.glob(f"{args.run_id}*.json"))
        if len(candidates) != 1:
            raise SystemExit(f"no unique run file for {args.run_id!r} in {RUNS_DIR}")
        path = candidates[0]
    run = json.loads(path.read_text())

    problems = validate(run, for_submission=True)
    if problems:
        for problem in problems:
            print(f"invalid: {problem}", file=sys.stderr)
        return 1

    system_id = run["system"]["id"]
    stamp = run["timestamp"].replace(":", "").replace("-", "")
    target = REPO_RESULTS / system_id / f"{stamp}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(run, indent=2) + "\n")
    print(f"wrote {target}")

    branch = f"result/{system_id}-{stamp}"
    if not shutil.which("gh"):
        print(
            "\ngh CLI not found. To publish by hand:\n"
            f"  git checkout -b {branch}\n"
            f"  git add {target}\n"
            f"  git commit -m 'result: {system_id} {run['timestamp']}'\n"
            f"  git push -u origin {branch}   # then open a pull request",
            file=sys.stderr,
        )
        return 0
    if args.dry_run:
        print(f"(dry run) would open a PR from branch {branch}")
        return 0
    repo = REPO_RESULTS.parent
    subprocess.run(["git", "checkout", "-b", branch], cwd=repo, check=True)
    subprocess.run(["git", "add", str(target)], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"result: {system_id} {run['timestamp']}"],
        cwd=repo, check=True,
    )
    subprocess.run(["git", "push", "-u", "origin", branch], cwd=repo, check=True)
    subprocess.run(
        ["gh", "pr", "create", "--fill",
         "--title", f"result: {run['system']['name']} {run['system']['version']}"],
        cwd=repo, check=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fmb", description=__doc__)
    parser.add_argument("--version", action="version", version=BENCH_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run the benchmark against a system")
    p_run.add_argument("--system", required=True,
                       help="http://host:port, module:Class, or `null`")
    p_run.add_argument("--families", help="comma-separated subset, e.g. C,A,T")
    p_run.add_argument("--seed", type=int, default=RELEASE_SEED,
                       help="override the release seed (makes the run unsubmittable)")
    p_run.add_argument("--repeat", type=int, default=1,
                       help="repeat every scenario N times and record the spread")
    p_run.add_argument("-v", "--verbose", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_val = sub.add_parser("validate", help="check run files against the schema")
    p_val.add_argument("paths", nargs="+")
    p_val.add_argument("--submission", action="store_true",
                       help="apply the stricter rules `fmb submit` applies")
    p_val.set_defaults(func=cmd_validate)

    p_ui = sub.add_parser("ui", help="build and open the results dashboard")
    p_ui.add_argument("--out", default="site")
    p_ui.add_argument("--no-open", action="store_true")
    p_ui.set_defaults(func=cmd_ui)

    p_sub = sub.add_parser("submit", help="publish a run to this repository")
    p_sub.add_argument("run_id")
    p_sub.add_argument("--dry-run", action="store_true")
    p_sub.set_defaults(func=cmd_submit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
