# Test Strategy

The generic test conventions (file naming, `all.py`, `run_cov_test`, coverage rules) are in `pywf-oss-base` (`10-test-layout.md`, `11-test-writing.md`, `12-coverage.md`). This file covers what is specific to this repo.

## 1. Everything runs on CI, and nothing calls real AWS

`mise run cov` and CI run the same `pytest tests`, with the `test`, `upload` and `publish` extras installed. Every AWS call goes to **moto**. There are no manual-only tests.

Tests come in three kinds:

| Kind | Files | How |
| :--- | :--- | :--- |
| Pure logic | `test_utils.py`, `test_*_foundation.py`, `test_layer_builder.py`, `test_layer_package.py`, `test_*_api.py` | `tmp_path`, fake files. `test_layer_builder.py` checks `docker_run_args` and the other computed properties; it never starts Docker. |
| Real local builds | `tests/source/test_source_builder.py` | Really runs `.venv/bin/pip` and `uv` (from `PATH`) to install **this repo itself** into `tests/source/build/lambda/source/using_pip|using_uv/`, then checks the tree, the zip, and that the SHA256 is stable. |
| AWS flows on moto | `test_source_upload.py`, `test_layer_upload.py`, `test_layer_publish.py` | Subclass `BaseMockAwsTest`; run the real upload / publish code against mocked S3 and Lambda. |

Requirements to run locally: the system `zip` binary, `uv` on `PATH`, and pip inside `.venv` (all present after `mise run inst`). No Docker and no AWS credentials.

## 2. `BaseMockAwsTest` (`aws_lbd_art_builder_core/tests/mock_aws.py`)

It lives in the package's `tests/` helper folder, which `pyproject.toml` excludes from the wheel: only this repo's tests can import it, not sub-packages.

- `setup_class` starts `moto.mock_aws()`, makes a `boto3.Session(region_name="us-east-1")`, and sets `cls.boto_ses` and `cls.s3_client`. It then calls `setup_class_post_hook()`.
- Subclasses override `setup_class_post_hook()` to create buckets (`cls.create_s3_bucket(name)`), make other clients (`cls.boto_ses.client("lambda")`), build fake inputs, and run the expensive flow **once**, storing the result on `cls`. Each `test_*` method then only asserts on that result.
- `teardown_class` stops the mock.
- `use_mock = False` on a subclass switches to real AWS through the `LOCAL_AWS_PROFILE` environment variable. Nothing in the repo uses it, and nothing cleans up what such a run creates. Do not commit a test with `use_mock = False`.

Fakes for the layer flow are tiny: `test_layer_publish.py::_create_fake_project` writes a one-line `pyproject.toml`, a fake `uv.lock`, and a `layer.zip` holding one file. The publisher never looks inside the zip, so this is enough to exercise the MD5 check, change detection, and the publish call.

## 3. Build output left on disk

The builder and publish tests write under `tests/source/build/` and `tests/layer/build/` and leave the output there for inspection. Each run cleans it first (`skip_prompt=True`). `build/` is git-ignored.

These folders contain **installed copies of this package's source**. A repo-wide `grep` will find old code in them; exclude `*/build/*` when searching.

## 4. What is not covered, on purpose

- `LayerDeploymentWorkflow` is `# pragma: no cover`: it only wires steps 2 to 4 around a builder, and each step is tested on its own.
- `clean_build_directory` and `prompt_to_confirm_before_remove_dir` are `# pragma: no cover` (interactive prompt).
- `verbose` printing branches in `source/` are `# pragma: no cover`.
- Docker container builds and real dependency installation (`uv sync`, `poetry install`) belong to the sub-packages' test suites.

## 5. Where a new test goes

- New logic in `layer/` or `source/` → the mirrored `tests/<sub>/test_<sub>_<module>.py`.
- Anything that touches S3 or Lambda → a `BaseMockAwsTest` subclass with a `setup_class_post_hook`. Use a bucket name unique to the class, since moto state is per class.
- New public name → also add it to the matching `test_*api.py`.
