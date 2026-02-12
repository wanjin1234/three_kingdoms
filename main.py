"""Project entry point for the refactored Three Kingdoms strategy game."""
from __future__ import annotations

import argparse
import logging
from typing import Final

from settings import SETTINGS
from src.core.app import GameApp


LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)7s | %(name)s | %(message)s"


def parse_cli_args() -> argparse.Namespace:
    """Parse CLI switches to tweak runtime behavior."""
    parser = argparse.ArgumentParser(
        prog="three_kingdoms",
        description="Launch the Three Kingdoms hex-strategy prototype",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose logging output for troubleshooting",
    )
    return parser.parse_args()


def configure_logging(debug: bool) -> None:
    """Configure root logging before any subsystems spin up."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format=LOG_FORMAT)
    logging.getLogger("pygame").setLevel(logging.WARNING)


def main() -> None:
    """Entrypoint that wires CLI, settings, and the GameApp together."""
    args = parse_cli_args()
    configure_logging(args.debug)

    logging.getLogger(__name__).info("Bootstrapping GameApp (debug=%s)", args.debug)
    app = GameApp(settings=SETTINGS, debug=args.debug)
    app.run()


if __name__ == "__main__":
    main()
