Code Architecture Design
==============================================================================

Package Family: 1 + N Design
------------------------------------------------------------------------------
``aws_lbd_art_builder_core`` is the **shared base** in a family of packages. The design follows a 1 + N pattern:

- **1 core package** (this one): tool-agnostic infrastructure — path layouts, S3 layouts, credentials, packaging, upload, publish, source artifact build
- **N tool-specific packages**: each implements Step 1 (dependency installation) and wires the 4-step workflow together

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Package
     - Role
   * - ``aws_lbd_art_builder_core``
     - Shared infrastructure (this package)
   * - ``aws_lbd_art_builder_uv``
     - UV-specific Step 1 builder + Workflow class
   * - ``aws_lbd_art_builder_poetry``
     - Poetry-specific Step 1 builder + Workflow class
   * - ``aws_lbd_art_builder_pip``
     - Pip-specific Step 1 builder + Workflow class

**Core never calls** ``pip install``, ``uv sync``, or ``poetry install`` directly. Those belong exclusively in tool-specific sub-packages.


Module Map
------------------------------------------------------------------------------
.. code-block:: text

    aws_lbd_art_builder_core/
    ├── constants.py        # ZFILL, S3MetadataKeyEnum, LayerBuildToolEnum
    ├── typehint.py         # T_PRINTER callable type alias
    ├── imports.py          # Conditional soft imports: S3Path, simple_aws_lambda
    ├── utils.py            # is_match, copy_source_for_lambda_deployment, write_bytes, ...
    ├── source.py           # Lambda function source artifact build/zip/upload workflow
    ├── layer/
    │   ├── foundation.py   # Credentials, LayerPathLayout, LayerS3Layout,
    │   │                   # BaseLogger, LayerManifestManager
    │   ├── builder.py      # BasedLambdaLayerLocalBuilder,
    │   │                   # BasedLambdaLayerContainerBuilder  (abstract bases)
    │   ├── package.py      # move_to_dir_python, create_layer_zip_file, LambdaLayerZipper
    │   ├── upload.py       # upload_layer_zip_to_s3
    │   └── publish.py      # LambdaLayerVersionPublisher, LayerDeployment
    └── vendor/
        ├── better_pathlib.py  # temp_cwd context manager
        ├── hashes.py          # hashes (MD5/SHA256 helper)
        └── timer.py           # DateTimeTimer


The 4-Step Lambda Layer Workflow
------------------------------------------------------------------------------
Every tool-specific sub-package follows this sequence:

.. code-block:: text

    Step 1 – Build    (sub-package)   install deps → build/lambda/layer/
    Step 2 – Package  (core)          zip → layer.zip
    Step 3 – Upload   (core)          push layer.zip → S3 (temp location)
    Step 4 – Publish  (core)          Lambda publish_layer_version API

Steps 2–4 are fully implemented in core. Sub-packages only implement Step 1.


Step 2 — Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:class:`~aws_lbd_art_builder_core.layer.package.LambdaLayerZipper` — core inputs:
``path_pyproject_toml``, ``layer_build_tool``, ``ignore_package_list``, ``verbose``.

- For ``uv``/``poetry``: calls :func:`~aws_lbd_art_builder_core.layer.package.move_to_dir_python` to relocate the venv's ``site-packages/`` → ``artifacts/python/``
- For ``pip``: packages are already in place; no move needed
- Creates ``build/lambda/layer/layer.zip`` with max compression, excluding :data:`~aws_lbd_art_builder_core.layer.package.default_ignore_package_list` (boto3, botocore, setuptools, pytest, …)


Step 3 — Upload
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:func:`~aws_lbd_art_builder_core.layer.upload.upload_layer_zip_to_s3` — core inputs:
``s3_client``, ``path_pyproject_toml``, ``s3dir_lambda``, ``layer_build_tool``.

- Uploads ``layer.zip`` to :attr:`~aws_lbd_art_builder_core.layer.foundation.LayerS3Layout.s3path_temp_layer_zip` (``${s3dir_lambda}/layer/layer.zip``)
- Stores the **manifest MD5** hash in S3 object metadata (key: ``S3MetadataKeyEnum.manifest_md5``) so Step 4 can verify consistency


Step 4 — Publish
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:class:`~aws_lbd_art_builder_core.layer.publish.LambdaLayerVersionPublisher` — core inputs:
``path_pyproject_toml``, ``s3dir_lambda``, ``layer_build_tool``, ``s3_client``,
``layer_name``, ``lambda_client``, ``publish_layer_version_kwargs``.

Three-stage preflight before publishing:

1. **Layer zip exists** — verifies ``layer.zip`` is present in S3
2. **Consistency check** — compares the manifest MD5 stored in S3 metadata against the local manifest; raises if they differ (catches stale or mismatched uploads)
3. **Change detection** — downloads the manifest stored alongside the *latest published layer version* and compares content; skips publish if identical

On success: stores the current manifest at ``${s3dir_lambda}/layer/{version:06d}/{manifest_filename}`` for future change detection, and returns :class:`~aws_lbd_art_builder_core.layer.publish.LayerDeployment` (``layer_name``, ``layer_version``, ``layer_version_arn``, ``s3path_manifest``).


Lambda Source Deployment Workflow
------------------------------------------------------------------------------
For deploying the Lambda **function code** (not its layer dependencies):

.. code-block:: text

    copy_source_for_lambda_deployment  ──►  pip install --no-deps  ──►  create_source_zip  ──►  upload_source_artifacts
    └─────────────────────── all wrapped in build_package_upload_source_artifacts ──────────────────────────────────────┘

:func:`~aws_lbd_art_builder_core.utils.copy_source_for_lambda_deployment` — inputs: ``source_dir``, ``target_dir``, ``include``, ``exclude`` (glob patterns).

- Always auto-excludes ``__pycache__/``, ``*.pyc``, ``*.pyo``
- Filtering rule: explicit exclude > explicit include > implicit include (see :func:`~aws_lbd_art_builder_core.utils.is_match`)

:func:`~aws_lbd_art_builder_core.source.build_package_upload_source_artifacts` — inputs: ``s3_client``, ``dir_project_root``, ``s3dir_lambda``.

- Installs the package with ``pip install --no-deps --target=...``
- Creates ``source.zip`` with SHA256 of the build directory
- Reads version from ``pyproject.toml``
- Uploads to ``${s3dir_lambda}/source/{version}/{sha256}/source.zip`` — the SHA256 in the path forces CDK/CloudFormation to detect code changes every time content changes


Path and S3 Layout Managers
------------------------------------------------------------------------------

LayerPathLayout (:mod:`aws_lbd_art_builder_core.layer.foundation`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:class:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout` is constructed from ``path_pyproject_toml`` and derives all local build paths:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Property
     - Resolved path
   * - :attr:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.dir_project_root`
     - ``pyproject.toml`` parent
   * - :attr:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.dir_build_lambda_layer`
     - ``{root}/build/lambda/layer/``
   * - :attr:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.dir_repo`
     - ``{layer}/repo/`` — isolated copy for dependency resolution
   * - :attr:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.dir_python`
     - ``{layer}/artifacts/python/`` — Lambda-required layout
   * - :attr:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.path_build_lambda_layer_zip`
     - ``{layer}/layer.zip``
   * - :attr:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.path_private_repository_credentials_in_local`
     - ``{build/lambda}/private-repository-credentials.json``

:meth:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.get_path_manifest` returns ``requirements.txt``, ``poetry.lock``, or ``uv.lock`` depending on the tool.

:meth:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.get_path_in_container` converts any local path to its Docker ``/var/task/...`` equivalent.


LayerS3Layout (:mod:`aws_lbd_art_builder_core.layer.foundation`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:class:`~aws_lbd_art_builder_core.layer.foundation.LayerS3Layout` is constructed from ``s3dir_lambda``:

.. list-table::
   :header-rows: 1
   :widths: 55 45

   * - Property / Method
     - S3 path
   * - :attr:`~aws_lbd_art_builder_core.layer.foundation.LayerS3Layout.s3path_temp_layer_zip`
     - ``{s3dir}/layer/layer.zip``
   * - :meth:`~aws_lbd_art_builder_core.layer.foundation.LayerS3Layout.get_s3dir_layer_version` ``(n)``
     - ``{s3dir}/layer/000001/`` (zero-padded with ``ZFILL=6``)
   * - :meth:`~aws_lbd_art_builder_core.layer.foundation.LayerS3Layout.get_s3path_layer_uv_lock` ``(n)``
     - ``{s3dir}/layer/000001/uv.lock``


Credentials (:mod:`aws_lbd_art_builder_core.layer.foundation`)
------------------------------------------------------------------------------
:class:`~aws_lbd_art_builder_core.layer.foundation.Credentials` is a frozen dataclass with fields:
``index_name``, ``index_url``, ``username``, ``password``.

Key derived values and methods:

- :attr:`~aws_lbd_art_builder_core.layer.foundation.Credentials.pip_extra_index_url` → ``https://{username}:{password}@{normalized_url}/simple/``
- :attr:`~aws_lbd_art_builder_core.layer.foundation.Credentials.additional_pip_install_args_index_url` / ``..._extra_index_url`` → ready-to-splice ``list[str]`` for ``pip install``
- :meth:`~aws_lbd_art_builder_core.layer.foundation.Credentials.poetry_login` → sets ``POETRY_HTTP_BASIC_{NAME}_USERNAME/PASSWORD`` env vars; returns ``(key_user, key_pass)``
- :meth:`~aws_lbd_art_builder_core.layer.foundation.Credentials.uv_login` → sets ``UV_INDEX_{NAME}_USERNAME/PASSWORD`` env vars
- :meth:`~aws_lbd_art_builder_core.layer.foundation.Credentials.dump` / :meth:`~aws_lbd_art_builder_core.layer.foundation.Credentials.load` → JSON serialization (used to pass credentials into Docker containers)


Abstract Base Classes for Sub-packages (:mod:`aws_lbd_art_builder_core.layer.builder`)
------------------------------------------------------------------------------

BasedLambdaLayerLocalBuilder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:class:`~aws_lbd_art_builder_core.layer.builder.BasedLambdaLayerLocalBuilder` — fields:
``path_pyproject_toml``, ``credentials``, ``skip_prompt``, ``_build_tool``.

Sub-packages **override** :meth:`~aws_lbd_art_builder_core.layer.builder.BasedLambdaLayerLocalBuilder.step_3_execute_build` with tool-specific installation logic. The inherited 4-step ``run()`` sequence:

1. ``step_1_preflight_check`` — print build info
2. ``step_2_prepare_environment`` — cleans ``dir_build_lambda_layer``, creates ``dir_repo`` and ``dir_python``
3. ``step_3_execute_build`` — **override this** (call pip/uv/poetry)
4. ``step_4_finalize_artifacts`` — **optionally override** (e.g. call :func:`~aws_lbd_art_builder_core.layer.package.move_to_dir_python` for uv/poetry)


BasedLambdaLayerContainerBuilder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:class:`~aws_lbd_art_builder_core.layer.builder.BasedLambdaLayerContainerBuilder` — fields:
``path_pyproject_toml``, ``py_ver_major``, ``py_ver_minor``, ``is_arm``, ``path_script``, ``credentials``.

Sub-packages supply ``path_script`` — the ``_build_lambda_layer_using_*_in_container.py`` file that runs inside Docker.

Key derived properties:

- :attr:`~aws_lbd_art_builder_core.layer.builder.BasedLambdaLayerContainerBuilder.image_uri` → ``public.ecr.aws/sam/build-python{M}.{m}:latest-{arch}``
- :attr:`~aws_lbd_art_builder_core.layer.builder.BasedLambdaLayerContainerBuilder.platform` → ``linux/amd64`` or ``linux/arm64``
- :attr:`~aws_lbd_art_builder_core.layer.builder.BasedLambdaLayerContainerBuilder.docker_run_args` → full ``docker run`` command list (mounts project root to ``/var/task``)

Step 2 copies the build script and dumps credentials JSON; Step 3 executes ``docker run``.


Public API by Audience (:mod:`aws_lbd_art_builder_core.api`)
------------------------------------------------------------------------------

**For end users** — configure, deploy source, run layer workflow Steps 2/3/4:

.. code-block:: python

    from aws_lbd_art_builder_core.api import (
        Credentials, LayerBuildToolEnum,
        copy_source_for_lambda_deployment,
        build_package_upload_source_artifacts, BuildSourceArtifactsResult,
        LambdaLayerZipper, default_ignore_package_list,
        upload_layer_zip_to_s3,
        LambdaLayerVersionPublisher, LayerDeployment,
    )

**For sub-package authors** — extend base classes, implement Step 1, assemble Workflow:

.. code-block:: python

    from aws_lbd_art_builder_core.api import (
        BasedLambdaLayerLocalBuilder, BasedLambdaLayerContainerBuilder,
        LayerPathLayout, move_to_dir_python,
        temp_cwd,                               # for container build scripts
        # pass-through to users:
        Credentials, LayerBuildToolEnum,
        LambdaLayerZipper, upload_layer_zip_to_s3,
        LambdaLayerVersionPublisher, LayerDeployment,
    )


Testing Philosophy
------------------------------------------------------------------------------
Core has **unit tests only** — no integration tests. Core never invokes pip/uv/poetry or makes real AWS calls.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Test file
     - What it covers
   * - ``tests/test_utils.py``
     - :func:`~aws_lbd_art_builder_core.utils.is_match`, :func:`~aws_lbd_art_builder_core.utils.copy_source_for_lambda_deployment`
   * - ``tests/test_source.py``
     - :class:`~aws_lbd_art_builder_core.source.SourceS3Layout` path construction (skipped if ``s3pathlib`` not installed)
   * - ``tests/test_layer_foundation.py``
     - :class:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout` paths, :class:`~aws_lbd_art_builder_core.layer.foundation.LayerS3Layout` S3 paths
   * - ``tests/test_credentials.py``
     - All :class:`~aws_lbd_art_builder_core.layer.foundation.Credentials` methods (pure logic + env vars + JSON roundtrip)
   * - ``tests/test_layer_package.py``
     - :func:`~aws_lbd_art_builder_core.layer.package.move_to_dir_python` (filesystem only)
   * - ``tests/test_container_builder.py``
     - :class:`~aws_lbd_art_builder_core.layer.builder.BasedLambdaLayerContainerBuilder` pure properties (image URI, platform, docker args)

Subprocess-calling functions (``create_layer_zip_file``, ``build_source_artifacts_using_pip``) and all AWS functions (``upload_layer_zip_to_s3``, ``LambdaLayerVersionPublisher``) are integration-level and belong in tool-specific sub-packages' test suites.
