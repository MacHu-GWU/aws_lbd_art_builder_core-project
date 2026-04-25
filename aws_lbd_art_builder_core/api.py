# -*- coding: utf-8 -*-

# ── For end users ─────────────────────────────────────────────────────────────
# Configure private repo credentials and select build tool
from .layer.foundation import Credentials
from .constants import LayerBuildToolEnum

# Deploy Lambda function source code
from .utils import copy_source_for_lambda_deployment
from .source import build_package_upload_source_artifacts
from .source import BuildSourceArtifactsResult

# Layer workflow: Step 2 - package, Step 3 - upload, Step 4 - publish
from .layer.package import LambdaLayerZipper
from .layer.package import default_ignore_package_list
from .layer.upload import upload_layer_zip_to_s3
from .layer.publish import LambdaLayerVersionPublisher
from .layer.publish import LayerDeployment

# ── For sub-package authors (pip / poetry / uv) ───────────────────────────────
# Extend these base classes to implement Step 1 (build)
from .layer.builder import BasedLambdaLayerLocalBuilder
from .layer.builder import BasedLambdaLayerContainerBuilder

# Used inside builder implementations and container build scripts
from .layer.foundation import LayerPathLayout
from .layer.package import move_to_dir_python
from .vendor.better_pathlib import temp_cwd

# ── Internal / advanced use ───────────────────────────────────────────────────
from .constants import ZFILL
from .constants import S3MetadataKeyEnum
from .typehint import T_PRINTER
from .utils import ensure_exact_one_true
from .utils import write_bytes
from .utils import is_match
from .utils import normalize_glob_patterns
from .utils import prompt_to_confirm_before_remove_dir
from .utils import clean_build_directory
from .source import SourcePathLayout
from .source import SourceS3Layout
from .source import build_source_artifacts_using_pip
from .source import create_source_zip
from .source import upload_source_artifacts
from .layer.foundation import LayerS3Layout
from .layer.foundation import BaseLogger
from .layer.foundation import LayerManifestManager
from .layer.package import create_layer_zip_file
from .vendor.hashes import hashes
from .vendor.timer import DateTimeTimer
