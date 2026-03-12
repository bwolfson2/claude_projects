"""Canonical slugify implementation for VFT fund tools.

All scripts should import from here to ensure consistent slug generation.
"""

import re


def slugify(text: str, max_length: int = 40) -> str:
    """Convert a name to a URL-safe slug.

    - Lowercases the input
    - Replaces non-alphanumeric sequences with a single hyphen
    - Strips leading/trailing hyphens
    - Collapses consecutive hyphens
    - Truncates to max_length characters (default 40)
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:max_length]
