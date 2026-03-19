"""CLI entry point for the bookkeeping tool.

Full argparse-based CLI is implemented in Phase 4. This module provides the
minimal entry point referenced by pyproject.toml and __main__.py.
"""

import sys


def main() -> None:
    """Run the bookkeeping CLI.

    Prints a usage message until the full CLI is implemented.
    """
    print(
        "bookkeeping — Swedish bookkeeping automation for GnuCash\n"
        "\n"
        "Usage:\n"
        "  bookkeeping import <csv_file>   Import bank transactions\n"
        "  bookkeeping report <type> <year> Generate PDF reports\n"
        "  bookkeeping rules               Manage categorization rules\n"
        "  bookkeeping config              View/set configuration\n"
        "  bookkeeping init                First-time setup\n"
        "\n"
        "Run 'bookkeeping init' to get started."
    )
    sys.exit(1)
