# How Sub-Packages Build on Core

What a tool-specific package (`aws_lbd_art_builder_uv`, `_pip`, `_poetry`) is expected to do with core. Read this before changing anything a sub-package depends on, or when helping write a new sub-package. The uv package (`../aws_lbd_art_builder_uv-project`, files under `aws_lbd_art_builder_uv/layer/`) is the working example; its own details are in its `maintain-aws_lbd_art_builder_uv` skill.

## 1. The sub-package's job: step 1 only

A sub-package provides one or two **builders** that turn `pyproject.toml` + a lock file into `LayerPathLayout.dir_python`. It then hands the builder to core's `LayerDeploymentWorkflow`, which does package, upload and publish.

Core has no base class for local builders (`BaseLambdaLayerLocalBuilder` was removed in 0.1.3). A builder only has to satisfy `T_BUILDER`: a `path_layout` property and a zero-argument `run()`.

## 2. Local builder pattern

As in `UvLambdaLayerLocalBuilder`, a frozen dataclass extending `layer_api.BaseLogger`, with `path_pyproject_toml`, `credentials`, `skip_prompt` and tool options as fields:

```python
@cached_property
def path_layout(self):
    return layer_api.LayerPathLayout(path_pyproject_toml=self.path_pyproject_toml)

def run(self):
    # 1. preflight: print / validate
    # 2. prepare:  path_layout.clean(skip_prompt=...); path_layout.mkdirs()
    #              path_layout.copy_pyproject_toml(); path_layout.copy_file(<lock file> → dir_repo)
    # 3. build:    credentials.uv_login() / poetry_login() / pip args; run the tool in dir_repo (temp_cwd)
    # 4. finalize: move_to_dir_python(path_layout.dir_build_lambda_layer_repo_venv_site_packages, path_layout.dir_python)
```

Pip-style builders can `pip install --target={dir_python}` and skip step 4.

## 3. Container builder pattern

Subclass `layer_api.BaseLambdaLayerContainerBuilder` (as `UvLambdaLayerContainerBuilder` does) and add `run()` plus any fields (`credentials`, tool options):

1. Prepare: `clean()` + `mkdirs()`; copy the sub-package's own container script to `path_build_lambda_layer_in_container_script_in_local`; if `credentials`, `credentials.dump(path_private_repository_credentials_in_local)`; copy `pyproject.toml` and the lock file into `dir_repo`.
2. Build: `subprocess.run(self.docker_run_args, check=True)`. Override `script_args` for options the script needs.
3. Finalize on the host: `move_to_dir_python(...)`, as in the local builder.

The container script runs inside the SAM image with only `dir_build_lambda_layer` mounted at `/var/task`. uv keeps it pure stdlib so it needs nothing from core or the sub-package installed in the image; it reads the credentials JSON itself.

## 4. Rules for sub-packages

- **Do not re-implement** zipping, uploading, publishing, path layouts or credential env vars. They are centralized so that a fix in core reaches every tool.
- **Use core's paths**, never hard-coded `build/lambda/layer/...` strings, so a layout change in core stays in one place.
- **Pass the tool's lock file as `path_manifest`** (`uv.lock`, `poetry.lock`, `requirements.txt`). Change detection depends on it describing the full dependency set.
- **Pin core to one major version** (`aws-lbd-art-builder-core>=X,<X+1`), and use core's `upload` / `publish` extras rather than listing `boto3` / `s3pathlib` versions separately, so the two never disagree.
- **Test helpers are not shared:** `aws_lbd_art_builder_core.tests` (including `BaseMockAwsTest`) is excluded from the wheel, so a sub-package cannot import it. A sub-package that needs mocked S3 or Lambda copies the class. uv does not need it today: its unit tests make no AWS calls.

## 5. What counts as a breaking change for sub-packages

When changing core, check the uv package for each of these. Any one of them needs a major version and a downstream update:

- A name removed or renamed in `api.py`, `layer_api` or `source_api`.
- A field, property or method removed or renamed on `LayerPathLayout`, `BaseLogger`, `BaseLambdaLayerContainerBuilder` or `Credentials` (sub-packages subclass or call these directly).
- A changed local path (`dir_repo`, `dir_python`, the container script or credentials file name) or S3 key layout.
- A changed `docker_run_args` shape, mount point or interpreter call, since the container script assumes them.
- A changed extra or its pinned libraries' major version (for example s3pathlib 2 → 3 in core 1.0.0, which also changed `bsm=` to `s3_client=` for anyone calling s3pathlib directly).

To find what a sub-package uses, search it for `layer_api.` and `source_api.`:

```bash
grep -rn "layer_api\.\|source_api\." ../aws_lbd_art_builder_uv-project/aws_lbd_art_builder_uv
```
