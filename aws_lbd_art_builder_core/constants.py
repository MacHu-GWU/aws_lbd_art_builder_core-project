# -*- coding: utf-8 -*-

import enum


ZFILL = 6


class S3MetadataKeyEnum(str, enum.Enum):
    """
    S3 Metadata Key Enum
    """
    source_version = "source_version"
    source_sha256 = "source_sha256"
    manifest_md5 = "manifest_md5"


class LayerBuildToolEnum(str, enum.Enum):
    """
    Layer Build Tool Enum
    """

    pip = "pip"
    poetry = "poetry"
    uv = "uv"
