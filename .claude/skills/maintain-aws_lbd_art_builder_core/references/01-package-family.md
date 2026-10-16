# The Package Family and This Package's Role

## 1. The 1 + N family

`aws_lbd_art_builder_core` is the shared base of a family of Lambda artifact builder packages:

| Package | Role |
| :--- | :--- |
| `aws_lbd_art_builder_core` | Tool-agnostic infrastructure (this repo) |
| `aws_lbd_art_builder_uv` | Builds the layer with `uv sync`, locally or in a container |
| `aws_lbd_art_builder_pip` | Builds the layer with `pip` (separate repo) |
| `aws_lbd_art_builder_poetry` | Builds the layer with `poetry` (separate repo) |

The uv package lives next to this repo, at `../aws_lbd_art_builder_uv-project`, and is the reference implementation of a sub-package. It has its own `maintain-aws_lbd_art_builder_uv` skill.

## 2. What core does and does not do

**Core owns:**

- Path conventions: where a build goes on disk (`LayerPathLayout`, `SourcePathLayout`) and in S3 (`LayerS3Layout`, `SourceS3Layout`).
- Layer steps 2 to 4: package `layer.zip`, upload it, publish a layer version (`02-layer-pipeline.md`).
- The end-to-end layer orchestrator `LayerDeploymentWorkflow`, which takes any builder through the `T_BUILDER` protocol.
- The container-build plumbing: SAM image URI, platform, `docker run` arguments (`BaseLambdaLayerContainerBuilder`).
- Private index credentials (`Credentials`) for pip, poetry and uv.
- The whole Lambda **source** (function code) workflow, for pip and uv (`03-source-pipeline.md`).

**Core never does:** resolve or install a project's dependencies for a layer. No `pip install -r`, `uv sync` or `poetry install` for layer building lives here. That is step 1, owned by each sub-package. (The source workflow does run `pip install --no-deps` / `uv pip install --no-deps`, but only to install the project itself, never its dependencies.)

When a change would add tool-specific layer logic to core, it belongs in a sub-package instead.

## 3. Module map

```text
aws_lbd_art_builder_core/
├── api.py              # Public API: top-level helpers + source_api / layer_api namespaces
├── constants.py        # ZFILL (=6), S3MetadataKeyEnum, LayerBuildToolEnum
├── typehint.py         # T_PRINTER
├── imports.py          # Soft imports: S3Path (extra "upload"), simple_aws_lambda (extra "publish")
├── utils.py            # is_match, copy_source_for_lambda_deployment, clean_build_directory, ...
├── paths.py            # path_enum: repo paths for tests and docs (not public)
├── source/
│   ├── foundation.py   # SourcePathLayout, SourceS3Layout
│   ├── builder.py      # build_source_dir_using_pip / _uv, create_source_zip
│   ├── upload.py       # upload_source_zip, build_and_upload_source_using_pip / _uv
│   └── api.py
├── layer/
│   ├── foundation.py   # Credentials, LayerPathLayout, LayerS3Layout, BaseLogger, LayerManifestManager
│   ├── builder.py      # BaseLambdaLayerContainerBuilder
│   ├── package.py      # move_to_dir_python, create_layer_zip_file, default_ignore_package_list
│   ├── upload.py       # upload_layer_zip_to_s3
│   ├── publish.py      # LambdaLayerVersionPublisher, LayerDeployment
│   ├── workflow.py     # T_BUILDER, LayerDeploymentWorkflow
│   └── api.py
├── tests/              # Test helpers for this repo's tests; excluded from the wheel (05-test-strategy.md)
└── vendor/             # better_pathlib.temp_cwd, hashes, timer, pytest_cov_helper
```

## 4. Public API shape

`aws_lbd_art_builder_core/api.py` exports a few top-level helpers (`ZFILL`, `S3MetadataKeyEnum`, `LayerBuildToolEnum`, `T_PRINTER`, the `utils` functions, `temp_cwd`, `hashes`, `DateTimeTimer`) and two **namespaces**:

```python
import aws_lbd_art_builder_core.api as aws_lbd_art_builder_core

aws_lbd_art_builder_core.layer_api.LayerDeploymentWorkflow
aws_lbd_art_builder_core.source_api.build_and_upload_source_using_uv
```

Layer and source names are reachable only through `layer_api` / `source_api`, never as flat imports from `api`. Sub-packages import core this way (see `aws_lbd_art_builder_uv/layer/local_builder.py`).

## 5. Optional dependencies

The runtime dependencies are only `func_args` and `soft_deps`. AWS-facing code needs extras:

| Extra | Adds | Needed by |
| :--- | :--- | :--- |
| `upload` | `boto3`, `s3pathlib` 3.x | anything that takes an `S3Path` or an `s3_client` |
| `publish` | `upload` + `simple_aws_lambda` | `LambdaLayerVersionPublisher`, `LayerDeploymentWorkflow` |

`imports.py` imports these softly. When an extra is missing, the name is a `soft_deps.MissingDependency` placeholder that raises on use, so `import aws_lbd_art_builder_core.api` always works.

`s3_client` arguments take a plain boto3 S3 client. s3pathlib 3.x calls take it as `s3_client=` (2.x used `bsm=`), and `BotoSesManager` is not accepted.

## 6. Compatibility with sub-packages

Each sub-package pins core to a major range (uv: `aws-lbd-art-builder-core>=0.1.5,<1.0.0` before 1.0.0). A breaking change to any name in `api.py`, to a path convention, or to the S3 layout breaks every sub-package and every already-deployed S3 layout. So:

- Changing a path or S3 key layout is a breaking change, even when no Python signature changes. Old layer versions' manifests sit at the old keys, and change detection will miss them.
- After a major release, each sub-package must raise its pin and adapt in its own repo.
- Record such changes under **Breaking Changes** in `release-history.rst`, with what downstream code must change.
