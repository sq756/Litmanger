"""Allow running Litmanger via `python -m litmanger`."""

from .cli import main
import sys

sys.exit(main())
