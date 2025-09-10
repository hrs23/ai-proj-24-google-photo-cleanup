#!/usr/bin/env python3
"""
Wrapper for tests defined in gphoto_cleanup.script.set_dates_from_folder
This file just imports the co-located tests for discovery.
"""

import sys
from pathlib import Path

# Add src package root to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from gphoto_cleanup.script.set_dates_from_folder import (  # noqa: F401
    TestFolderDateInferenceProcessor,
)

