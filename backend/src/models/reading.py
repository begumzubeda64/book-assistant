"""Shared reading enums.

Reading modes map to the ~3/5/10-minute experience (product.md). Defined here so
progress, adaptive reading, and jobs can all reference the same identifiers.
"""

from __future__ import annotations

from enum import StrEnum


class ReadingMode(StrEnum):
    QUICK_READ = "quick_read"
    BALANCED_READ = "balanced_read"
    DEEP_READ = "deep_read"
