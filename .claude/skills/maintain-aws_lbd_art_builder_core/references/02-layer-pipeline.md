# The Lambda Layer Pipeline

Code: `aws_lbd_art_builder_core/layer/`. Step 1 is owned by a sub-package; steps 2 to 4 live here.

## 1. The four steps

```text
Step 1  Build    (sub-package builder)   install deps        → build/lambda/layer/artifacts/python/
Step 2  Package  (package.py)            zip python/         → build/lambda/layer/layer.zip
Step 3  Upload   (upload.py)             layer.zip + md5     → ${s3dir_lambda}/layer/layer.zip
Step 4  Publish  (publish.py)            publish_layer_version, store manifest → ${s3dir_lambda}/layer/{000001}/{manifest}
```

`LayerDeploymentWorkflow` (`workflow.py`) runs all four in `run()`, and each one alone as `step_1_build()` … `step_4_publish()`. Its fields: `builder`, `path_manifest`, `s3dir_lambda`, `layer_name`, `s3_client`, `lambda_client`, and optional `ignore_package_list`, `publish_layer_version_kwargs`. Steps 2 to 4 read every local path from `builder.path_layout`.

**The builder is duck-typed.** `T_BUILDER` is a `runtime_checkable` Protocol: any object with a `path_layout` (a `LayerPathLayout`) and a zero-argument `run()` works. Core does not subclass or call any other builder method.

**The manifest** (`path_manifest`) is the tool's lock or requirements file: `uv.lock`, `poetry.lock`, `requirements.txt`. Core never parses it. It only hashes it (step 3) and compares and stores its bytes (step 4).

## 2. Local paths: `LayerPathLayout` (`foundation.py`)

Built from `path_pyproject_toml`; everything derives from `dir_project_root = path_pyproject_toml.parent`:

| Property | Path |
| :--- | :--- |
| `dir_build_lambda` | `{root}/build/lambda` |
| `dir_build_lambda_layer` | `{root}/build/lambda/layer`, wiped by `clean()` before each build |
| `path_build_lambda_layer_zip` | `{layer}/layer.zip` |
| `dir_repo` | `{layer}/repo`, an isolated copy of the project files the tool needs |
| `path_tmp_pyproject_toml` | `{layer}/repo/pyproject.toml` |
| `dir_artifacts` | `{layer}/artifacts` |
| `dir_python` | `{layer}/artifacts/python`, the Lambda-required top-level folder |
| `dir_build_lambda_layer_repo_venv_site_packages` | `{layer}/repo/.venv/lib/pythonX.Y/site-packages` |
| `path_build_lambda_layer_in_container_script_in_local` | `{layer}/build_lambda_layer_in_container.py` |
| `path_private_repository_credentials_in_local` | `{layer}/private-repository-credentials.json` |

Helpers: `clean(skip_prompt)`, `mkdirs()` (creates `dir_repo` and `dir_python`), `copy_file()`, `copy_pyproject_toml()`, `copy_build_script()`.

Gotchas:

- `dir_build_lambda_layer_repo_venv_site_packages` finds `X.Y` by running the **host** project's `{root}/.venv/bin/python --version` (`venv_python_version`). The layer venv must use the same minor version, including in container builds. POSIX layout only (no Windows, see `CLAUDE.md`).
- `get_path_in_container(p)` maps a path **relative to `dir_build_lambda_layer`** to `/var/task/...`, because only that folder is mounted into the container. It raises `ValueError` for paths outside it.

## 3. S3 paths: `LayerS3Layout` (`foundation.py`)

Built from `s3dir_lambda` (a shared parent; source artifacts live beside it under `source/`):

| Member | S3 path |
| :--- | :--- |
| `s3path_temp_layer_zip` | `{s3dir_lambda}/layer/layer.zip`, overwritten on every upload |
| `get_s3dir_layer_version(n)` | `{s3dir_lambda}/layer/{n:06d}/` (`ZFILL = 6`) |
| `get_s3path_layer_manifest(n, name)` | `{s3dir_lambda}/layer/{n:06d}/{name}` |

Only one `layer.zip` is kept: AWS stores published layer content itself. The per-version folders keep only the manifest, for change detection.

## 4. Step 2: Package (`package.py`)

- `move_to_dir_python(dir_site_packages, dir_python)`: **moves** (not copies) a venv's `site-packages` to `dir_python`, replacing it. A no-op if both are the same path. Raises `FileNotFoundError` if the source is missing. Used by venv-based tools (uv, poetry); `pip install --target` can write to `dir_python` directly.
- `create_layer_zip_file(dir_python, path_layer_zip, ignore_package_list, verbose)`: runs the system `zip -r -9` from inside `dir_artifacts` (`temp_cwd`), so entries start with `python/`. Each ignored name becomes `-x python/{name}*`, a **prefix** match: `pip` also drops `pipx`, `pip_*` and so on.
- `default_ignore_package_list`: `boto3`, `botocore`, `s3transfer`, `urllib3` (in the Lambda runtime), `setuptools`, `pip`, `wheel`, `twine`, `_pytest`, `pytest`.

## 5. Step 3: Upload (`upload.py`)

`upload_layer_zip_to_s3(s3_client, path_pyproject_toml, s3dir_lambda, path_manifest, ...)` uploads `layer.zip` to `s3path_temp_layer_zip` with `ContentType: application/zip`, and stores the manifest's MD5 in object metadata under `S3MetadataKeyEnum.manifest_md5`. That MD5 is the link between the zip in S3 and the manifest on disk.

`LayerManifestManager` (`foundation.py`) is the shared base for upload and publish: fields `path_pyproject_toml`, `s3dir_lambda`, `path_manifest`, `s3_client`; it gives `path_layout`, `s3_layout`, `manifest_md5`, and `get_versioned_manifest(version)`.

## 6. Step 4: Publish (`publish.py`)

`LambdaLayerVersionPublisher(LayerManifestManager)` adds `layer_name`, `lambda_client`, `publish_layer_version_kwargs`. `run()`:

1. **Preflight**, read-only:
   1. `layer.zip` exists at `s3path_temp_layer_zip`, or `FileNotFoundError`.
   2. Its `manifest_md5` metadata equals the local manifest's MD5, or `ValueError`. Catches a stale zip from another build.
   3. The local manifest differs from the one stored for the **latest published layer version** (`simple_aws_lambda.get_latest_layer_version`), or `ValueError`. No previous version, or no stored manifest, counts as changed.
2. **Publish**: `lambda_client.publish_layer_version(LayerName, Content={S3Bucket, S3Key}, **publish_layer_version_kwargs)`, then write the manifest to `get_versioned_manifest(new_version)`.
3. Return `LayerDeployment(layer_name, layer_version, layer_version_arn, s3path_manifest)`.

**"No changes" is an exception, not a skip.** When the manifest is unchanged, check 1.3 raises `ValueError("Dependencies unchanged since last publication - skipping")`, so `LayerDeploymentWorkflow.run()` raises too. Callers that want a soft skip must catch it.

Layer versions are append-only in AWS, which is why the publisher refuses to publish an unchanged manifest.

## 7. Container builds: `BaseLambdaLayerContainerBuilder` (`builder.py`)

A frozen dataclass (extends `BaseLogger`) with `path_pyproject_toml`, `py_ver_major`, `py_ver_minor`, `is_arm`. It computes only Docker settings; the build steps belong to the sub-package's subclass.

| Member | Value |
| :--- | :--- |
| `path_layout` | `LayerPathLayout(path_pyproject_toml)` |
| `image_uri` | `public.ecr.aws/sam/build-python{M}.{m}:latest-{x86_64,arm64}` |
| `platform` | `linux/amd64` or `linux/arm64` |
| `container_name` | `lambda_layer_builder-python{M}{m}-{amd64,arm64}` |
| `script_args` | `[]`; override to pass options to the container script (uv passes `--extra ...`) |
| `docker_run_args` | `docker run --rm --name … --platform … --mount type=bind,source={dir_build_lambda_layer},target=/var/task {image} python -u /var/task/build_lambda_layer_in_container.py *script_args` |

Contract with the subclass:

- Copy its container script to `path_build_lambda_layer_in_container_script_in_local` (`copy_build_script()`), and everything the script needs into `dir_build_lambda_layer`. Nothing else is visible inside the container.
- Pass credentials through a file: `Credentials.dump(path_private_repository_credentials_in_local)`, then `Credentials.load(...)` in the container. Never put secrets in `script_args`: `docker run` arguments show up in process listings.

## 8. `Credentials` (`foundation.py`)

A frozen dataclass: `index_name`, `index_url`, `username`, `password`.

- `normalized_index_url`: strips `https://`, a trailing `/` and `/simple`.
- `pip_extra_index_url`: `https://{username}:{password}@{normalized}/simple/`. `additional_pip_install_args_index_url` / `..._extra_index_url` give `["--index-url" | "--extra-index-url", url]`.
- `uv_login()` / `poetry_login()`: set `UV_INDEX_{NAME}_USERNAME/PASSWORD` or `POETRY_HTTP_BASIC_{NAME}_USERNAME/PASSWORD` in `os.environ`, where `NAME` is `index_name` upper-cased with `-` → `_`. **The username is hard-coded to `"aws"`** (AWS CodeArtifact convention), not `self.username`.
- `dump(path)` / `load(path)`: JSON round trip.

## 9. Logging

`BaseLogger` (`verbose`, `printer`) gives `log`, `log_header`, `log_sub_header`, `log_detail`. Every command-style class extends it, so a sub-package's builder can share the same output style. Pass `printer=` to redirect output (tests pass a no-op).
