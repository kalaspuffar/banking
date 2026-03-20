"""Bookkeeping — Swedish bookkeeping automation tools for GnuCash."""

import warnings

# Suppress piecash/SQLAlchemy relationship overlap warnings. These arise
# from piecash's GnuCash ORM mapping where multiple models share the
# polymorphic slots table. The warnings are harmless and cannot be fixed
# without patching piecash itself.
warnings.filterwarnings(
    "ignore",
    message=r"relationship '.*' will copy column",
    category=DeprecationWarning,
    module=r"piecash\..*",
)
warnings.filterwarnings(
    "ignore",
    message=r"relationship '.*' will copy column",
    category=FutureWarning,
    module=r"piecash\..*",
)

# SAWarning is only available when SQLAlchemy is installed
try:
    from sqlalchemy.exc import SAWarning
    warnings.filterwarnings(
        "ignore",
        message=r"relationship '.*' will copy column",
        category=SAWarning,
    )
except ImportError:
    pass

__version__ = "0.1.0"
