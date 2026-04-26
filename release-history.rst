.. _release_history:

Release and Version History
==============================================================================


x.y.z (Backlog)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

**Minor Improvements**

**Bugfixes**

**Miscellaneous**


0.1.2 (2026-04-26)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Breaking Changes**

- Removed ``LambdaLayerZipper`` class — replaced by direct functions ``create_layer_zip_file()`` and ``move_to_dir_python()``. Sub-packages now call these functions directly instead of dispatching through an enum-based class.
- Renamed ``BasedLambdaLayerLocalBuilder`` → ``BaseLambdaLayerLocalBuilder`` and ``BasedLambdaLayerContainerBuilder`` → ``BaseLambdaLayerContainerBuilder`` (fixed spelling).
- Removed ``layer_build_tool: LayerBuildToolEnum`` parameter from ``upload_layer_zip_to_s3()`` and ``LambdaLayerVersionPublisher`` — replaced by generic ``path_manifest: Path`` so core never needs to know which tool built the layer.
- Removed tool-specific properties and methods from ``LayerPathLayout`` (``path_requirements_txt``, ``path_poetry_toml``, ``path_poetry_lock``, ``path_uv_lock``, ``copy_poetry_toml``, ``copy_poetry_lock``, ``copy_uv_lock``, ``get_path_manifest``). Sub-packages should manage their own tool-specific file paths.
- Restructured ``api.py`` — source and layer sub-module APIs are now exposed as ``source_api`` and ``layer_api`` namespace objects instead of flat re-exports.

**Features and Improvements**

- Refactored ``source`` module from a single file into a proper package (``source/foundation.py``, ``source/builder.py``, ``source/upload.py``, ``source/api.py``).
- Added ``BaseMockAwsTest`` test base class using moto for mock S3/Lambda services, enabling unit-level testing of AWS-calling code.
- Added ``source/upload.py`` with ``build_and_upload_source_using_pip()`` and ``build_and_upload_source_using_uv()`` convenience functions.
- Added ``layer/api.py`` as centralized public API module for the layer sub-package.
- Added Sub-Package Extension Guide (``docs/source/99-Maintainer-Guide/03-Sub-Package-Extension-Guide/``) documenting how tool-specific packages should extend core.

**Minor Improvements**

- Made ``LayerManifestManager`` accept generic ``path_manifest: Path`` instead of ``LayerBuildToolEnum``, making manifest handling fully tool-agnostic.
- Added ``LayerPathLayout.copy_file()`` and ``LayerPathLayout.copy_build_script()`` utility methods for sub-package use.
- Updated Code Architecture Design doc to reflect all refactored class names, removed classes, and new test file structure.
- Comprehensive test suite for all layer sub-modules (foundation, builder, package, upload, publish) achieving 99% coverage.


0.1.1 (2026-04-25) (YANKED)
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
