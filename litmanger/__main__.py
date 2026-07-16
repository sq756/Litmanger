"""Allow running Litmanger via `python -m litmanger`."""

import sys

from .cli import main

sys.exit(main())
