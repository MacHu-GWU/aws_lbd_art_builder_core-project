.. _release_history:

Release and Version History
==============================================================================


x.y.z (Backlog)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

**Minor Improvements**

**Bugfixes**

**Miscellaneous**


0.1.1 (2026-04-25)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- Initial release of ``aws_lbd_art_builder_core``, the shared base in the 1+N Lambda artifact builder package family.
- Implemented the 4-step Lambda layer workflow: package (Step 2), upload (Step 3), publish (Step 4). Step 1 (dependency installation) is delegated to tool-specific sub-packages (``uv``, ``pip``, ``poetry``).
- Implemented Lambda source artifact deployment workflow: copy/filter source, ``pip install --no-deps``, zip, upload to S3 with SHA256 in the path for CDK/CloudFormation change detection.
- Added ``LayerPathLayout`` and ``LayerS3Layout`` for deterministic local and S3 path management.
- Added ``Credentials`` frozen dataclass supporting private PyPI index authentication for pip, poetry, and uv.
- Added ``LambdaLayerVersionPublisher`` with three-stage preflight: zip existence check, manifest MD5 consistency check, and dependency change detection to skip unnecessary layer publishes.
- Added ``BasedLambdaLayerLocalBuilder`` and ``BasedLambdaLayerContainerBuilder`` abstract base classes for sub-package authors.
- Added ``LambdaLayerZipper`` (Step 2) with configurable ignore list (excludes boto3, botocore, setuptools, pytest, etc.).
