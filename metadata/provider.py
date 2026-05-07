"""
metadata/provider.py
Move từ v2/metadata.py — schema metadata provider cho toàn hệ thống.
Re-export từ v2/metadata để duy trì single source of truth.
"""
# Re-export from v2/metadata.py — single source of truth
from v2.metadata import MetadataProvider, load_v2_metadata, V2Metadata

__all__ = ["MetadataProvider", "load_v2_metadata", "V2Metadata"]
