# The Lambda Source Pipeline

Code: `aws_lbd_art_builder_core/source/`. This deploys the Lambda **function code** (the project's own package), not its dependencies; those go in the layer (`02-layer-pipeline.md`). Unlike the layer pipeline, all of it, including the build, lives in core, for pip and uv.

## 1. Assumptions

- The project has a `pyproject.toml` with a `[build-system]` table; `setup.py`-only projects are not supported.
- The Lambda handler lives **inside** the installed package.
- The build backend decides which files ship (`packages.find`, `package-data`).
- The system `zip` binary is on `PATH`.

## 2. Flow

```text
build_source_dir_using_pip / _uv   install the project, no deps → {dir_root}/build/
create_source_zip                  zip build/ → {dir_root}/source.zip, return sha256 of build/
upload_source_zip                  → {s3dir_source}/{version}/{sha256}/source.zip
```

`build_and_upload_source_using_pip` / `_uv` chain the three and return `BuildAndUploadSourceResult(source_sha256, s3path_source_zip)`. They take `s3_client`, `dir_project_root`, `s3dir_source`, `skip_prompt`, `verbose`, `printer` (the uv one also takes `path_bin_uv`, e.g. `Path(shutil.which("uv"))`). They use `{root}/build/lambda/source` as the layout root and read `[project].version` from `pyproject.toml`. The pip one always uses `{root}/.venv/bin/pip`.

## 3. Layouts (`foundation.py`)

Both are pure path computation, with no I/O.

- `SourcePathLayout(dir_root)`: `dir_build = {dir_root}/build`, `path_source_zip = {dir_root}/source.zip`. The zip is a **sibling** of `build/`, so it never zips itself.
- `SourceS3Layout(dir_root)`: `dir_root` is already scoped to source, e.g. `s3://bucket/app/lambda/source/`. `from_s3dir_lambda(s3dir_lambda)` derives it as `{s3dir_lambda}/source/`, a sibling of the layer's `{s3dir_lambda}/layer/`. `get_s3path_source_zip(version, sha256)` → `{dir_root}/{version}/{sha256}/source.zip`.

The SHA256 in the key is deliberate: any code change gives a new S3 key, so CDK / CloudFormation see a change and redeploy the function.

## 4. Build (`builder.py`)

- `build_source_dir_using_pip(path_bin_pip, path_pyproject_toml, dir_lambda_source_build, ...)`: `pip install {project_dir} --no-dependencies --target={dir}`.
- `build_source_dir_using_uv(path_bin_uv, ...)`: `uv pip install {project_dir} --no-deps --target={dir}`. Needs no pip in the venv.
- Both first wipe the target with `clean_build_directory`. Without `skip_prompt=True` it asks on stdin, and raises `RuntimeError` on "no".
- They install rather than copy files so that package metadata and `*.dist-info` match what the runtime imports.
- `create_source_zip(dir_lambda_source_build, path_source_zip, ...)`: `zip -r -9` run inside the build dir (`temp_cwd`), so entries sit at the zip root. The returned SHA256 is `hashes.of_paths([build_dir])`, computed over the **directory**, not the zip, so zip timestamps do not change it.

## 5. Upload (`upload.py`)

`upload_source_zip(s3_client, source_version, source_sha256, path_source_zip, s3dir_source, metadata, tags, ...)`:

- `ContentType: application/zip`.
- Metadata always includes `S3MetadataKeyEnum.source_version` and `source_sha256`; a caller's `metadata` dict is merged on top.
- `tags` are URL-encoded into the `Tagging` extra arg.
- Overwrites an existing object at the same key (same version and hash means same content).

## 6. Copying a source tree: `utils.copy_source_for_lambda_deployment`

Not part of the pip/uv flow above, but exported for callers that build a deployment folder by copying files.

- `include` / `exclude` take a glob or a list (`normalize_glob_patterns`). `__pycache__/*`, `*.pyc`, `*.pyo` are always excluded.
- Rule (`is_match`): explicit exclude > explicit include > implicit include. Matching uses `Path.match`, which anchors at the **end** of the relative path (`*.py` matches at any depth).
- The docstring says the target is "completely replaced", but the code only writes matching files; it does not delete existing files in the target. Clean it first if stale files matter.
