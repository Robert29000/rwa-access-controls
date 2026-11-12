"""CLI: python -m rwa_access [--providers robinhood,xstocks] [--out output]"""

import argparse
import logging
from pathlib import Path

from rwa_access.config import DEFAULT_ABI_DIR, DEFAULT_CONFIG_DIR, ConfigError
from rwa_access.output.csv_out import write_csv
from rwa_access.output.markdown import write_markdown
from rwa_access.providers import load_providers


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and validate stock-token role holders.")
    parser.add_argument(
        "--providers",
        help="Comma-separated provider names (file names in <config>/providers/). Default: all.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_DIR, help="Config directory.")
    parser.add_argument("--abis", type=Path, default=DEFAULT_ABI_DIR, help="ABI directory.")
    parser.add_argument("--out", type=Path, default=Path("output"), help="Output directory.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )
    try:
        providers = load_providers(args.config, args.abis)
    except ConfigError as exc:
        parser.exit(2, f"Config error: {exc}\n")

    names = list(providers)
    if args.providers:
        names = [name.strip() for name in args.providers.split(",") if name.strip()]
        unknown = [name for name in names if name not in providers]
        if unknown:
            parser.error(f"Unknown provider(s): {', '.join(unknown)}. Available: {', '.join(providers)}")

    results = [providers[name].run() for name in names]
    paths = write_csv(results, args.out)
    paths.append(write_markdown(results, args.out / "report.md"))
    for result in results:
        failed = [h for h in result.holders if not h.validated]
        logging.info(
            "%s: %d assignments, %d not validated", result.provider, len(result.holders), len(failed)
        )
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
