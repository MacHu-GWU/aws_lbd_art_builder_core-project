# aws_lbd_art_builder_core 1.0.0: public API reference

Import only through `aws_lbd_art_builder_core.api`:

```python
import aws_lbd_art_builder_core.api as aws_lbd_art_builder_core
from aws_lbd_art_builder_core.api import layer_api
from aws_lbd_art_builder_core.api import source_api
```

## Conventions that apply everywhere

- **Extras.** Without extras only path, zip and utility code works. Anything taking an `S3Path` or `s3_client` needs `pip install "aws_lbd_art_builder_core[upload]"` (boto3, s3pathlib 3.x). Publishing needs `[publish]` (adds simple_aws_lambda). A missing extra makes the name a placeholder that raises on use, so imports never fail.
- **Clients.** `s3_client` / `lambda_client` are plain boto3 clients (`boto3.Session().client("s3")`). A `BotoSesManager` is not accepted.
- **S3 locations** are `s3pathlib.api.S3Path`. Directories should end with `/`, e.g. `S3Path("s3://bucket/app/lambda/")`.
- **Dataclasses.** Command and layout classes are frozen dataclasses built on `func_args.BaseFrozenModel`: pass fields by keyword. An omitted required field raises `func_args` `ParamError`. `Credentials` and `LayerS3Layout` are plain dataclasses.
- **Logging.** Command classes take `verbose: bool = True` and `printer: Callable[[str], None] = print`. Pass `printer=lambda msg: None` to silence them.
- **System tools.** Zipping shells out to the `zip` binary. POSIX only (no Windows).
- **Paths on disk.** Layer builds use `{project_root}/build/lambda/layer/`; source builds use `{project_root}/build/lambda/source/`. Both are wiped before each build, after a stdin prompt unless `skip_prompt=True`.

## S3 layout written by this library

```text
{s3dir_lambda}/layer/layer.zip                    # latest uploaded layer zip, overwritten each upload
{s3dir_lambda}/layer/000001/{manifest_filename}   # lock file stored per published layer version
{s3dir_lambda}/source/{version}/{sha256}/source.zip
```

---

## Layer: `layer_api`

### `LayerDeploymentWorkflow`

```python
LayerDeploymentWorkflow(
    builder: T_BUILDER,                       # required
    path_manifest: Path,                      # required: uv.lock / poetry.lock / requirements.txt
    s3dir_lambda: S3Path,                     # required
    layer_name: str,                          # required
    s3_client: S3Client,                      # required
    lambda_client: LambdaClient,              # required
    ignore_package_list: list[str] | None = None,   # None → default_ignore_package_list
    publish_layer_version_kwargs: dict | None = None,
    verbose: bool = True,
    printer = print,
)
.run() -> LayerDeployment
.step_1_build() / .step_2_package() / .step_3_upload() / .step_4_publish() -> LayerDeployment
```

The one-call layer pipeline. `builder` is any object with a `path_layout: LayerPathLayout` property and a zero-argument `run()` that fills `path_layout.dir_python`; sub-packages provide one (e.g. `aws_lbd_art_builder_uv.api.layer_api.UvLambdaLayerLocalBuilder`). Steps 2 to 4 take every local path from `builder.path_layout`.

`publish_layer_version_kwargs` go straight to boto3 `publish_layer_version` (e.g. `CompatibleRuntimes`, `CompatibleArchitectures`, `Description`, `LicenseInfo`). `LayerName` and `Content` are set for you.

**Gotcha:** when `path_manifest` is byte-identical to the one stored for the latest published version, `run()` raises `ValueError("Dependencies unchanged since last publication - skipping")` after building, packaging and uploading. Catch it for a soft skip, or call `LambdaLayerVersionPublisher(...).has_dependency_manifest_changed()` first.

```python
from pathlib import Path
import boto3
from s3pathlib.api import S3Path
import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv
from aws_lbd_art_builder_core.api import layer_api

boto_ses = boto3.Session(region_name="us-east-1")
builder = aws_lbd_art_builder_uv.layer_api.UvLambdaLayerLocalBuilder(
    path_pyproject_toml=Path("pyproject.toml"),
    skip_prompt=True,
)
workflow = layer_api.LayerDeploymentWorkflow(
    builder=builder,
    path_manifest=Path("uv.lock"),
    s3dir_lambda=S3Path("s3://my-bucket/projects/my_app/lambda/"),
    layer_name="my_app",
    s3_client=boto_ses.client("s3"),
    lambda_client=boto_ses.client("lambda"),
    publish_layer_version_kwargs={"CompatibleRuntimes": ["python3.12"]},
)
try:
    deployment = workflow.run()
    print(deployment.layer_version_arn)
except ValueError as e:
    print(f"not published: {e}")
```

### `LambdaLayerVersionPublisher`

```python
LambdaLayerVersionPublisher(
    path_pyproject_toml: Path, s3dir_lambda: S3Path, path_manifest: Path,
    s3_client: S3Client, layer_name: str, lambda_client: LambdaClient,  # all required
    publish_layer_version_kwargs: dict | None = None,
    verbose: bool = True, printer = print,
)
.run() -> LayerDeployment
.is_layer_zip_exists() -> bool               # {s3dir_lambda}/layer/layer.zip exists
.is_layer_zip_consistent() -> bool           # its manifest_md5 metadata == MD5 of the local manifest
.has_dependency_manifest_changed() -> bool   # differs from the latest published version's stored manifest
.latest_layer_version                        # simple_aws_lambda.LayerVersion | None (cached)
```

Step 4 alone, for an already-uploaded `layer.zip`. `run()` checks, in order: zip exists (else `FileNotFoundError`), zip is consistent (else `ValueError`: the zip was built from a different lock file), manifest changed (else `ValueError`). Then it publishes, stores the manifest at `{s3dir_lambda}/layer/{version:06d}/{manifest name}`, and returns a `LayerDeployment`. A first publish (no versions yet) always counts as changed.

```python
publisher = layer_api.LambdaLayerVersionPublisher(
    path_pyproject_toml=path_pyproject_toml,
    s3dir_lambda=s3dir_lambda,
    path_manifest=path_manifest,
    s3_client=s3_client,
    layer_name="my_layer",
    lambda_client=lambda_client,
    verbose=False,
)
if publisher.has_dependency_manifest_changed():
    deployment = publisher.run()
```

### `LayerDeployment`

```python
LayerDeployment(layer_name: str, layer_version: int, layer_version_arn: str, s3path_manifest: S3Path)
```

Frozen result of a publish. `s3path_manifest` is where the lock file for this version was stored.

### `upload_layer_zip_to_s3`

```python
upload_layer_zip_to_s3(
    s3_client: S3Client, path_pyproject_toml: Path, s3dir_lambda: S3Path, path_manifest: Path,
    verbose: bool = True, printer = print,
) -> None
```

Step 3. Uploads `{project_root}/build/lambda/layer/layer.zip` to `{s3dir_lambda}/layer/layer.zip` (overwrite), with `ContentType=application/zip` and metadata `manifest_md5` = MD5 of `path_manifest`. Upload and publish must use the same manifest file, or the publisher's consistency check fails.

### `create_layer_zip_file`, `move_to_dir_python`, `default_ignore_package_list`

```python
create_layer_zip_file(dir_python: Path, path_layer_zip: Path, ignore_package_list: list[str] | None = None, verbose: bool = True) -> None
move_to_dir_python(dir_site_packages: Path, dir_python: Path) -> None
default_ignore_package_list = ["boto3", "botocore", "s3transfer", "urllib3", "setuptools", "pip", "wheel", "twine", "_pytest", "pytest"]
```

- `create_layer_zip_file`: zips `dir_python` with `zip -r -9`, run from its parent folder so entries start with `python/` (what Lambda expects under `/opt/python`). Each ignored name excludes `python/{name}*`: a **prefix** match, so `"pip"` also drops `pipx`. `None` uses the default list (packages the Lambda runtime already has, plus build and test tools). Pass `[]` to exclude nothing.
- `move_to_dir_python`: **moves** a venv's `site-packages` folder to `dir_python`, replacing it. No-op when both are the same path. Raises `FileNotFoundError` if the source is missing.

```python
layer_api.create_layer_zip_file(
    dir_python=path_layout.dir_python,
    path_layer_zip=path_layout.path_build_lambda_layer_zip,
    ignore_package_list=["boto3", "botocore"],
    verbose=False,
)
```

### `LayerPathLayout`

```python
LayerPathLayout(path_pyproject_toml: Path)   # required; everything derives from its parent folder
```

| Member | Value |
| :--- | :--- |
| `dir_project_root` | `path_pyproject_toml.parent` |
| `dir_venv`, `path_venv_bin_python` | `{root}/.venv`, `{root}/.venv/bin/python` |
| `venv_python_version` | `(major, minor, micro)` from running `path_venv_bin_python --version` |
| `dir_build_lambda` | `{root}/build/lambda` |
| `dir_build_lambda_layer` | `{root}/build/lambda/layer` (mounted into container builds) |
| `path_build_lambda_layer_zip` | `{layer}/layer.zip` |
| `dir_repo` | `{layer}/repo`: copy of the files the tool needs |
| `path_tmp_pyproject_toml` | `{layer}/repo/pyproject.toml` |
| `dir_artifacts`, `dir_python` | `{layer}/artifacts`, `{layer}/artifacts/python` |
| `dir_build_lambda_layer_repo_venv_site_packages` | `{layer}/repo/.venv/lib/python{X.Y}/site-packages`, `X.Y` from the **project's** `.venv` |
| `path_build_lambda_layer_in_container_script_in_local` / `..._in_container` | `{layer}/build_lambda_layer_in_container.py` / `/var/task/build_lambda_layer_in_container.py` |
| `path_private_repository_credentials_in_local` / `..._in_container` | `{layer}/private-repository-credentials.json` / `/var/task/...` |

Methods: `clean(skip_prompt=False)` deletes `dir_build_lambda_layer` (prompts unless `skip_prompt`; raises `RuntimeError` on "no"). `mkdirs()` creates `dir_repo` and `dir_python`. `copy_file(p_src, p_dst, printer=print)`, `copy_pyproject_toml(printer=print)`, `copy_build_script(p_src, printer=print)`. `get_path_in_container(path_in_local) -> str` maps a path under `dir_build_lambda_layer` to `/var/task/...` and raises `ValueError` for anything outside it.

```python
path_layout = layer_api.LayerPathLayout(path_pyproject_toml=Path("/repo/pyproject.toml"))
path_layout.dir_python                                       # /repo/build/lambda/layer/artifacts/python
path_layout.get_path_in_container(path_layout.dir_repo / "uv.lock")   # "/var/task/repo/uv.lock"
```

### `LayerS3Layout`

```python
LayerS3Layout(s3dir_lambda: S3Path)
.s3path_temp_layer_zip -> S3Path                                         # {s3dir_lambda}/layer/layer.zip
.get_s3dir_layer_version(layer_version: int) -> S3Path                    # {s3dir_lambda}/layer/000001/
.get_s3path_layer_manifest(layer_version: int, manifest_filename: str) -> S3Path   # .../000001/uv.lock
```

Pure path computation, no AWS call.

### `LayerManifestManager`

```python
LayerManifestManager(path_pyproject_toml: Path, s3dir_lambda: S3Path, path_manifest: Path, s3_client: S3Client, verbose=True, printer=print)
.path_layout -> LayerPathLayout
.s3_layout -> LayerS3Layout
.manifest_md5 -> str                                  # MD5 hex of path_manifest (cached)
.get_versioned_manifest(version: int) -> S3Path        # where that version's manifest is stored
```

Base class of `LambdaLayerVersionPublisher`; rarely used directly.

### `Credentials`

```python
Credentials(index_name: str, index_url: str, username: str, password: str)   # frozen
.normalized_index_url -> str          # strips "https://", trailing "/" and "/simple"
.uppercase_index_name -> str          # "my-repo" → "MY_REPO"
.pip_extra_index_url -> str           # "https://{username}:{password}@{normalized}/simple/"
.additional_pip_install_args_index_url -> list[str]        # ["--index-url", url]
.additional_pip_install_args_extra_index_url -> list[str]  # ["--extra-index-url", url]
.uv_login() -> tuple[str, str]        # sets UV_INDEX_{NAME}_USERNAME / _PASSWORD in os.environ
.poetry_login() -> tuple[str, str]    # sets POETRY_HTTP_BASIC_{NAME}_USERNAME / _PASSWORD
.dump(path: Path) -> None             # JSON, creates parent folders
Credentials.load(path: Path) -> Credentials
```

**Gotcha:** `uv_login()` and `poetry_login()` always set the username to `"aws"` (AWS CodeArtifact convention), not `username`. They return the two environment variable names. `index_name` must match the index name in `pyproject.toml` for uv / poetry to pick the variables up.

```python
cred = layer_api.Credentials(
    index_name="my-private-repo",
    index_url="https://my-private-repo.example.com/simple/",
    username="aws",
    password=token,
)
cred.pip_extra_index_url   # "https://aws:<token>@my-private-repo.example.com/simple/"
cred.dump(path_layout.path_private_repository_credentials_in_local)   # hand to a container build
```

### `BaseLambdaLayerContainerBuilder`

```python
BaseLambdaLayerContainerBuilder(path_pyproject_toml: Path, py_ver_major: int, py_ver_minor: int, is_arm: bool, verbose=True, printer=print)
.path_layout -> LayerPathLayout
.image_tag -> str          # "latest-arm64" / "latest-x86_64"
.image_uri -> str          # "public.ecr.aws/sam/build-python3.12:latest-x86_64"
.platform -> str           # "linux/arm64" / "linux/amd64"
.container_name -> str     # "lambda_layer_builder-python312-amd64"
.script_args -> list[str]  # [] ; override to pass options to the container script
.docker_run_args -> list[str]
```

Base for Docker-based builders in sub-packages; it has no `run()`. `docker_run_args` is `docker run --rm --name {container_name} --platform {platform} --mount type=bind,source={dir_build_lambda_layer},target=/var/task {image_uri} python -u /var/task/build_lambda_layer_in_container.py *script_args`. Only `dir_build_lambda_layer` is visible inside the container, so a subclass copies its script and inputs there first. Never put secrets in `script_args` (visible in process listings); use `Credentials.dump()` instead.

```python
builder = layer_api.BaseLambdaLayerContainerBuilder(
    path_pyproject_toml=Path("/repo/pyproject.toml"),
    py_ver_major=3, py_ver_minor=12, is_arm=False,
)
subprocess.run(builder.docker_run_args, check=True)
```

### `BaseLogger`

```python
BaseLogger(verbose: bool = True, printer: Callable[[str], None] = print)
.log(msg) / .log_header(title) / .log_sub_header(title) / .log_detail(msg)
```

Mixin for consistent build output; a sub-package's builder can extend it. Nothing prints when `verbose=False`.

---

## Source: `source_api`

Deploys the Lambda **function code**: the project installed with no dependencies (those go in the layer). Requires a `pyproject.toml` with `[build-system]`, the handler inside the package, and the `zip` binary.

### `build_and_upload_source_using_uv` / `build_and_upload_source_using_pip`

```python
build_and_upload_source_using_uv(
    s3_client: S3Client, path_bin_uv: Path, dir_project_root: Path, s3dir_source: S3Path,
    skip_prompt: bool = False, verbose: bool = True, printer = print,
) -> BuildAndUploadSourceResult
build_and_upload_source_using_pip(
    s3_client: S3Client, dir_project_root: Path, s3dir_source: S3Path,
    skip_prompt: bool = False, verbose: bool = True, printer = print,
) -> BuildAndUploadSourceResult
```

Install into `{root}/build/lambda/source/build/`, zip to `{root}/build/lambda/source/source.zip`, read `[project].version`, upload to `{s3dir_source}/{version}/{sha256}/source.zip`. The pip variant always uses `{root}/.venv/bin/pip`. `s3dir_source` is the **source-scoped** folder; derive it with `SourceS3Layout.from_s3dir_lambda(s3dir_lambda).dir_root`.

The SHA256 in the key changes whenever the code changes, so CDK / CloudFormation pick up a new deployment.

```python
import shutil
from aws_lbd_art_builder_core.api import source_api

s3dir_source = source_api.SourceS3Layout.from_s3dir_lambda(
    S3Path("s3://my-bucket/projects/my_app/lambda/")
).dir_root
result = source_api.build_and_upload_source_using_uv(
    s3_client=s3_client,
    path_bin_uv=Path(shutil.which("uv")),
    dir_project_root=Path("/repo"),
    s3dir_source=s3dir_source,
    skip_prompt=True,
    verbose=False,
)
result.source_sha256, result.s3path_source_zip.uri
```

### `BuildAndUploadSourceResult`

```python
BuildAndUploadSourceResult(source_sha256: str, s3path_source_zip: S3Path)
```

### Lower-level steps

```python
build_source_dir_using_uv(path_bin_uv: Path, path_pyproject_toml: Path, dir_lambda_source_build: Path, skip_prompt=False, verbose=True, printer=print) -> None
build_source_dir_using_pip(path_bin_pip: Path, path_pyproject_toml: Path, dir_lambda_source_build: Path, skip_prompt=False, verbose=True, printer=print) -> None
create_source_zip(dir_lambda_source_build: Path, path_source_zip: Path, verbose=True, printer=print) -> str
upload_source_zip(
    s3_client: S3Client, source_version: str, source_sha256: str, path_source_zip: Path, s3dir_source: S3Path,
    metadata: dict[str, str] | None = None, tags: dict[str, str] | None = None, verbose=True, printer=print,
) -> S3Path
```

- `build_source_dir_*`: wipe the folder, then `uv pip install {project} --no-deps --target=...` / `pip install {project} --no-dependencies --target=...`.
- `create_source_zip`: zip entries sit at the zip root. Returns the SHA256 of the **build folder** (not the zip), so it is stable across zip timestamps. `path_source_zip` must not be inside the build folder.
- `upload_source_zip`: `ContentType=application/zip`; metadata always has `source_version` and `source_sha256`, merged with `metadata`; `tags` become the S3 object tags. Overwrites an existing object at the same key.

### `SourcePathLayout`, `SourceS3Layout`

```python
SourcePathLayout(dir_root: Path)        # e.g. {root}/build/lambda/source
.dir_build -> Path                      # {dir_root}/build
.path_source_zip -> Path                # {dir_root}/source.zip

SourceS3Layout(dir_root: S3Path)        # source-scoped, e.g. s3://bucket/app/lambda/source/
SourceS3Layout.from_s3dir_lambda(s3dir_lambda: S3Path) -> SourceS3Layout   # dir_root = {s3dir_lambda}/source/
.get_s3path_source_zip(source_version: str, source_sha256: str) -> S3Path  # {dir_root}/{version}/{sha256}/source.zip
```

---

## Top level: `aws_lbd_art_builder_core.api`

### File copy and matching

```python
copy_source_for_lambda_deployment(source_dir: str | Path, target_dir: str | Path, include: str | list[str] | None = None, exclude: str | list[str] | None = None) -> None
is_match(relpath_parts: list[str], include: list[str], exclude: list[str]) -> bool
normalize_glob_patterns(patterns: str | list[str] | None) -> list[str]
```

`copy_source_for_lambda_deployment` copies every file under `source_dir` that `is_match` accepts, keeping the tree. `__pycache__/*`, `*.pyc`, `*.pyo` are always excluded. Existing files in `target_dir` are **not** deleted; clean it first if needed.

`is_match` returns `True` to include. Rule: explicit exclude > explicit include > implicit include (no include patterns means include all). Patterns use `PurePath.match`, anchored at the end of the path: `"*.py"` matches at any depth, and `"docs/*"` matches files directly inside any `docs` folder (`a/docs/x.md` yes, `docs/x/y.md` no).

```python
aws_lbd_art_builder_core.copy_source_for_lambda_deployment(
    source_dir="./my_package",
    target_dir="./build/my_package",
    include=["*.py"],
    exclude=["*test*"],
)
aws_lbd_art_builder_core.is_match(["a", "b.py"], include=["*.py"], exclude=[])   # True
```

### Build folder helpers

```python
clean_build_directory(dir_build: Path, folder_alias: str, skip_prompt: bool = False) -> None
prompt_to_confirm_before_remove_dir(dir_path: Path) -> bool   # stdin "Y/N"
write_bytes(path: Path, content: bytes) -> None               # creates parent folders
ensure_exact_one_true(lst: list[bool]) -> None                 # ValueError unless exactly one True
temp_cwd(path: str | Path)                                     # context manager; NotADirectoryError if not a dir
```

`clean_build_directory` deletes `dir_build` if it exists; without `skip_prompt` it asks on stdin and raises `RuntimeError` on "no".

### `hashes`

A ready `Hashes` instance (SHA256, hex digest by default). Each method also takes `algo=` (`HashAlgoEnum`) and `hexdigest=`:

```python
hashes.of_str(s) / hashes.of_bytes(b) / hashes.of_file(path) / hashes.of_folder(path) / hashes.of_paths([path, ...])
```

`of_folder` / `of_paths` hash files in sorted path order, so the result is stable.

### `DateTimeTimer`

```python
DateTimeTimer(title: str | None = None, verbose: bool = True, start: bool = True)
.start() / .end()   # end() sets .elapsed (seconds) and prints when verbose
with DateTimeTimer(title="build"):
    ...
```

### Constants and types

```python
ZFILL = 6                                   # zero padding of layer version folders
S3MetadataKeyEnum.source_version / .source_sha256 / .manifest_md5   # str enum, S3 metadata keys
LayerBuildToolEnum.pip / .poetry / .uv      # str enum
T_PRINTER = Callable[[str], None]
```
