---
name: maintain-aws_lbd_art_builder_core
description: "Project-specific knowledge for maintaining the aws_lbd_art_builder_core repo, the shared base of the 1+N Lambda artifact builder family (uv, pip, poetry sub-packages): what core owns versus the sub-packages, the Lambda layer pipeline (LayerPathLayout and LayerS3Layout, packaging layer.zip, upload with manifest MD5, publish with change detection, LayerDeploymentWorkflow and the T_BUILDER protocol, the container builder, Credentials), the Lambda source pipeline (pip / uv install, source.zip with SHA256, S3 layout), the contract with sub-packages and what breaks them, and the test strategy (moto, real local builds, BaseMockAwsTest). Use before changing the library code, fixing a bug in it, reviewing a change to it, writing or fixing its tests, changing something a sub-package depends on, or when someone asks how this project works."
---

Knowledge that only this repo needs. The conventions shared by every pywf open-source library (layout, code style, tests, docs, CI, release, dependencies) are in `pywf-oss-base`, not here; load that skill for them.

## The project in three lines

- Core is the tool-agnostic base of the family: path and S3 layouts, packaging, upload, publish, credentials, and the container-build plumbing. Sub-packages (`aws_lbd_art_builder_uv`, ...) only install dependencies for a layer (step 1).
- Layer: a builder fills `build/lambda/layer/artifacts/python/`, then `LayerDeploymentWorkflow` zips it, uploads it with the lock file's MD5, and publishes a new layer version only when the lock file changed.
- Source: core installs the project itself (no dependencies) with pip or uv, zips it, and uploads it to `{version}/{sha256}/source.zip`.

## Which reference to read

| When | Read |
| :--- | :--- |
| Deciding whether something belongs in core, touching `api.py`, the extras, or `imports.py` | [references/01-package-family.md](references/01-package-family.md) |
| Changing, fixing, or reviewing code in `layer/` | [references/02-layer-pipeline.md](references/02-layer-pipeline.md) |
| Changing, fixing, or reviewing code in `source/` or `utils.copy_source_for_lambda_deployment` | [references/03-source-pipeline.md](references/03-source-pipeline.md) |
| Changing anything a sub-package uses (public names, paths, S3 layout, container builder, extras), or helping write a sub-package | [references/01-package-family.md](references/01-package-family.md), then [references/04-sub-package-extension.md](references/04-sub-package-extension.md) |
| Writing or fixing tests, or deciding where a test goes | [references/05-test-strategy.md](references/05-test-strategy.md) |
| Answering "how does this project work?" | all five, in order |

## Related skills

- `pywf-oss-base`: repo-wide conventions, and which `pywf-oss-*` skill does which job (add a module, write tests, write docs, changelog, release).
- `pypi-s3pathlib`: the `S3Path` API used for every S3 path and call here.
- `maintain-aws_lbd_art_builder_uv`, in `../aws_lbd_art_builder_uv-project`: how the uv sub-package builds layers on top of core.
