"""
metadata/__init__.py
Package metadata — schema metadata provider.
"""
from metadata.provider import MetadataProvider, load_v2_metadata, V2Metadata

__all__ = ["MetadataProvider", "load_v2_metadata", "V2Metadata"]
