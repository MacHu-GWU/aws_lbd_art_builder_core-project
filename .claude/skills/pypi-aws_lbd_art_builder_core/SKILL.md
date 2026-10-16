---
name: pypi-aws_lbd_art_builder_core
description: Python library aws_lbd_art_builder_core, the tool-agnostic core for building and deploying AWS Lambda artifacts. Build, zip and upload a Lambda function's source code with pip or uv, and package, upload and publish a Lambda layer with change detection, given a dependency builder from a sub-package such as aws_lbd_art_builder_uv. Public symbols include LayerDeploymentWorkflow, LambdaLayerVersionPublisher, LayerDeployment, upload_layer_zip_to_s3, create_layer_zip_file, move_to_dir_python, LayerPathLayout, LayerS3Layout, Credentials, BaseLambdaLayerContainerBuilder, BaseLogger, build_and_upload_source_using_uv, build_and_upload_source_using_pip, SourcePathLayout, SourceS3Layout, copy_source_for_lambda_deployment, temp_cwd, hashes. Generated for aws_lbd_art_builder_core version 1.0.0. Higher 1.x versions should generally be compatible, lower versions may still work but correctness is not guaranteed.
---

# aws_lbd_art_builder_core

Core of a 1+N family of Lambda artifact builders. **Layer**: a sub-package's builder (e.g. `aws_lbd_art_builder_uv`) installs dependencies into `build/lambda/layer/artifacts/python/`; core zips it, uploads it to S3 with the lock file's MD5, and publishes a new layer version only if the lock file changed. **Source**: core installs the project itself (no dependencies) with pip or uv, zips it, and uploads it to `{version}/{sha256}/source.zip`. Core never installs a layer's dependencies itself. AWS calls need the extras `upload` (boto3, s3pathlib 3.x) and `publish` (+ simple_aws_lambda). Pass plain boto3 clients; S3 locations are `s3pathlib.api.S3Path`.

## Import

```python
from aws_lbd_art_builder_core.api import layer_api
from aws_lbd_art_builder_core.api import source_api
import aws_lbd_art_builder_core.api as aws_lbd_art_builder_core     # then aws_lbd_art_builder_core.layer_api.X
```

Layer and source symbols are reached only through the `layer_api` / `source_api` namespaces.

## Public API

Classes are dataclasses: pass fields by keyword; fields marked `*` are required. Command classes also take `verbose: bool = True` and `printer: Callable[[str], None] = print`.

### `layer_api`

- `LayerDeploymentWorkflow(builder*, path_manifest*, s3dir_lambda*, layer_name*, s3_client*, lambda_client*, ignore_package_list=None, publish_layer_version_kwargs=None)`: build, package, upload and publish in one call.
  - `.run() -> LayerDeployment`; also `.step_1_build()`, `.step_2_package()`, `.step_3_upload()`, `.step_4_publish() -> LayerDeployment`.
  - `builder`: any object with `.path_layout: LayerPathLayout` and `.run()` (the `T_BUILDER` protocol).
  - Raises `ValueError` when the manifest is unchanged since the last published version.
- `LambdaLayerVersionPublisher(path_pyproject_toml*, s3dir_lambda*, path_manifest*, s3_client*, layer_name*, lambda_client*, publish_layer_version_kwargs=None)`: step 4 alone. `.run() -> LayerDeployment`; `.is_layer_zip_exists() -> bool`; `.is_layer_zip_consistent() -> bool`; `.has_dependency_manifest_changed() -> bool`.
- `LayerDeployment(layer_name, layer_version: int, layer_version_arn, s3path_manifest: S3Path)`: result of a publish.
- `upload_layer_zip_to_s3(s3_client, path_pyproject_toml, s3dir_lambda, path_manifest, verbose=True, printer=print)`: step 3.
- `create_layer_zip_file(dir_python, path_layer_zip, ignore_package_list=None, verbose=True)`: step 2; needs the `zip` binary.
- `move_to_dir_python(dir_site_packages, dir_python)`: move a venv's site-packages to `python/`.
- `default_ignore_package_list: list[str]`: boto3, botocore, s3transfer, urllib3, setuptools, pip, wheel, twine, _pytest, pytest.
- `LayerPathLayout(path_pyproject_toml*)`: local build paths under `{root}/build/lambda/layer/`. Main members: `dir_build_lambda_layer`, `dir_repo`, `dir_python`, `path_build_lambda_layer_zip`, `dir_build_lambda_layer_repo_venv_site_packages`, `clean(skip_prompt=False)`, `mkdirs()`, `copy_pyproject_toml()`, `copy_file(p_src, p_dst)`, `get_path_in_container(path) -> str`.
- `LayerS3Layout(s3dir_lambda)`: `.s3path_temp_layer_zip`, `.get_s3dir_layer_version(n)`, `.get_s3path_layer_manifest(n, filename)`.
- `LayerManifestManager(path_pyproject_toml*, s3dir_lambda*, path_manifest*, s3_client*)`: base of the publisher. `.path_layout`, `.s3_layout`, `.manifest_md5`, `.get_versioned_manifest(version) -> S3Path`.
- `Credentials(index_name, index_url, username, password)`: private package index auth. `.pip_extra_index_url`, `.additional_pip_install_args_index_url`, `.additional_pip_install_args_extra_index_url`, `.uv_login()`, `.poetry_login()`, `.dump(path)`, `Credentials.load(path)`.
- `BaseLambdaLayerContainerBuilder(path_pyproject_toml*, py_ver_major*, py_ver_minor*, is_arm*)`: base for Docker builds. `.path_layout`, `.image_uri`, `.platform`, `.container_name`, `.script_args` (override), `.docker_run_args`.
- `BaseLogger(verbose=True, printer=print)`: `.log(msg)`, `.log_header(title)`, `.log_sub_header(title)`, `.log_detail(msg)`.

### `source_api`

- `build_and_upload_source_using_uv(s3_client, path_bin_uv, dir_project_root, s3dir_source, skip_prompt=False, verbose=True, printer=print) -> BuildAndUploadSourceResult`: install, zip and upload in one call.
- `build_and_upload_source_using_pip(s3_client, dir_project_root, s3dir_source, skip_prompt=False, verbose=True, printer=print) -> BuildAndUploadSourceResult`: the same, using `{root}/.venv/bin/pip`.
- `BuildAndUploadSourceResult(source_sha256: str, s3path_source_zip: S3Path)`.
- `build_source_dir_using_uv(path_bin_uv, path_pyproject_toml, dir_lambda_source_build, skip_prompt=False, verbose=True, printer=print)` / `build_source_dir_using_pip(path_bin_pip, ...)`: install the project with no dependencies into a folder.
- `create_source_zip(dir_lambda_source_build, path_source_zip, verbose=True, printer=print) -> str`: zip it and return its SHA256.
- `upload_source_zip(s3_client, source_version, source_sha256, path_source_zip, s3dir_source, metadata=None, tags=None, verbose=True, printer=print) -> S3Path`.
- `SourcePathLayout(dir_root*)`: `.dir_build`, `.path_source_zip`.
- `SourceS3Layout(dir_root*)`: `SourceS3Layout.from_s3dir_lambda(s3dir_lambda)`, `.get_s3path_source_zip(version, sha256) -> S3Path`.

### Top level

- `copy_source_for_lambda_deployment(source_dir, target_dir, include=None, exclude=None)`: copy a tree, filtered by globs.
- `is_match(relpath_parts, include, exclude) -> bool`; `normalize_glob_patterns(patterns) -> list[str]`.
- `clean_build_directory(dir_build, folder_alias, skip_prompt=False)`; `prompt_to_confirm_before_remove_dir(dir_path) -> bool`.
- `write_bytes(path, content)`: write, creating parent folders. `ensure_exact_one_true(lst)`.
- `temp_cwd(path)`: context manager that changes the working directory.
- `hashes`: hash helper, e.g. `hashes.of_paths([dir])`, `hashes.of_file(path)`.
- `DateTimeTimer(title=None, verbose=True, start=True)`: elapsed-time timer, also a context manager.
- `ZFILL = 6`; `S3MetadataKeyEnum` (`source_version`, `source_sha256`, `manifest_md5`); `LayerBuildToolEnum` (`pip`, `poetry`, `uv`); `T_PRINTER = Callable[[str], None]`.

## More detail

For signatures, semantics, gotchas and examples see `ref/public-api.md`. The library has no CLI.
