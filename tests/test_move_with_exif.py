#!/usr/bin/env python3
"""
Wrapper for tests defined in gphoto_cleanup.script.move_with_exif
This file just imports the co-located tests for discovery.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add src package root to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from gphoto_cleanup.script.move_with_exif import (  # noqa: F401
    TestExifFileMover,
)
