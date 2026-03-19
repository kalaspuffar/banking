"""CLI entry point for the bokföring tool.

Full argparse-based CLI is implemented in Phase 4. This module provides the
minimal entry point referenced by pyproject.toml and __main__.py.
"""

import sys


def main() -> None:
    """Run the bokföring CLI.

    Prints a usage message until the full CLI is implemented.
    """
    print(
        "bokforing — Swedish bookkeeping automation for GnuCash\n"
        "\n"
        "Usage:\n"
        "  bokforing import <csv_file>   Import bank transactions\n"
        "  bokforing report <type> <year> Generate PDF reports\n"
        "  bokforing rules               Manage categorization rules\n"
        "  bokforing config              View/set configuration\n"
        "  bokforing init                First-time setup\n"
        "\n"
        "Run 'bokforing init' to get started."
    )
    sys.exit(0)
