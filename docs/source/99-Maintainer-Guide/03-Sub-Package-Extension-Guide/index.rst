Sub-Package Extension Guide
==============================================================================

This guide explains how tool-specific sub-packages (``aws_lbd_art_builder_uv``,
``aws_lbd_art_builder_pip``, ``aws_lbd_art_builder_poetry``) should extend
``aws_lbd_art_builder_core`` to implement Lambda layer building.

**Core's responsibility**: define conventions (path layouts, S3 layouts), provide
tool-agnostic infrastructure (zip, upload, publish, credentials).

**Sub-package's responsibility**: implement Step 1 (dependency installation) using
the specific tool, then wire the 4-step workflow together.


What Core Provides
------------------------------------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Import
     - Purpose
   * - :class:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout`
     - Local directory conventions: ``dir_python``, ``dir_repo``, ``path_build_lambda_layer_zip``, etc.
   * - :class:`~aws_lbd_art_builder_core.layer.foundation.LayerS3Layout`
     - S3 path conventions: ``s3path_temp_layer_zip``, ``get_s3dir_layer_version``, ``get_s3path_layer_manifest``
   * - :class:`~aws_lbd_art_builder_core.layer.foundation.Credentials`
     - Private repository auth: ``pip_extra_index_url``, ``poetry_login``, ``uv_login``, ``dump``/``load``
   * - :class:`~aws_lbd_art_builder_core.layer.builder.BaseLambdaLayerLocalBuilder`
     - Abstract base for local builds (4-step workflow)
   * - :class:`~aws_lbd_art_builder_core.layer.builder.BaseLambdaLayerContainerBuilder`
     - Abstract base for Docker-based builds (4-step workflow)
   * - :func:`~aws_lbd_art_builder_core.layer.package.move_to_dir_python`
     - Relocate ``site-packages/`` into ``python/`` for Lambda
   * - :func:`~aws_lbd_art_builder_core.layer.package.create_layer_zip_file`
     - Create ``layer.zip`` with package exclusions
   * - :data:`~aws_lbd_art_builder_core.layer.package.default_ignore_package_list`
     - Default packages to exclude (boto3, pytest, etc.)
   * - :func:`~aws_lbd_art_builder_core.layer.upload.upload_layer_zip_to_s3`
     - Upload ``layer.zip`` to S3 staging location
   * - :class:`~aws_lbd_art_builder_core.layer.publish.LambdaLayerVersionPublisher`
     - Smart publish with change detection
   * - :class:`~aws_lbd_art_builder_core.layer.publish.LayerDeployment`
     - Immutable result of a successful publish
   * - :class:`~aws_lbd_art_builder_core.layer.workflow.LayerDeploymentWorkflow`
     - One-stop orchestrator: Build → Package → Upload → Publish in a single ``run()``
   * - :class:`~aws_lbd_art_builder_core.layer.workflow.T_BUILDER`
     - Protocol for builders (requires ``.run()`` and ``.path_layout``)

All imports are available from ``aws_lbd_art_builder_core.layer.api``.


What Sub-Packages Must Implement
------------------------------------------------------------------------------

Each sub-package needs to implement **Step 1 — Build**: the tool-specific logic
that installs dependencies into the layer build directory.

The minimum implementation is a subclass of
:class:`~aws_lbd_art_builder_core.layer.builder.BaseLambdaLayerLocalBuilder`
that overrides three methods:


step_2_prepare_environment — Copy Tool-Specific Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The base class handles ``clean()`` + ``mkdirs()`` + ``copy_pyproject_toml()``.
Sub-packages should call ``super()`` and then copy their own lock files:

.. code-block:: python

    def step_2_prepare_environment(self):
        super().step_2_prepare_environment()
        # uv needs uv.lock in the isolated build dir
        self.path_layout.copy_file(
            p_src=self.path_layout.dir_project_root / "uv.lock",
            p_dst=self.path_layout.dir_repo / "uv.lock",
        )


step_3_execute_build — Run the Tool
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the core of the sub-package. Run the tool-specific commands to install
dependencies:

.. code-block:: python

    def step_3_execute_build(self):
        super().step_3_execute_build()
        dir_repo = self.path_layout.dir_repo
        # Create a venv and install deps using uv
        subprocess.run(
            ["uv", "venv", str(dir_repo / ".venv")],
            cwd=str(dir_repo), check=True,
        )
        subprocess.run(
            ["uv", "pip", "install", "-r", "pyproject.toml",
             "--python", str(dir_repo / ".venv" / "bin" / "python")],
            cwd=str(dir_repo), check=True,
        )


step_4_finalize_artifacts — Relocate Packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the tool installs packages into ``site-packages/`` (uv, poetry do this),
they need to be moved into the ``python/`` directory that Lambda requires:

.. code-block:: python

    def step_4_finalize_artifacts(self):
        super().step_4_finalize_artifacts()
        move_to_dir_python(
            dir_site_packages=self.path_layout.dir_build_lambda_layer_repo_venv_site_packages,
            dir_python=self.path_layout.dir_python,
        )

.. note::

    ``pip`` with ``--target`` installs directly into ``dir_python``, so pip-based
    builders typically skip this step.


Full Example: UvLambdaLayerLocalBuilder
------------------------------------------------------------------------------

.. code-block:: python

    import subprocess
    import dataclasses
    from pathlib import Path

    from aws_lbd_art_builder_core.layer.api import BaseLambdaLayerLocalBuilder
    from aws_lbd_art_builder_core.layer.api import move_to_dir_python


    @dataclasses.dataclass(frozen=True)
    class UvLambdaLayerLocalBuilder(BaseLambdaLayerLocalBuilder):
        """Build a Lambda layer using uv on the local machine."""

        path_bin_uv: Path = dataclasses.field(default=None)

        def step_2_prepare_environment(self):
            super().step_2_prepare_environment()
            self.path_layout.copy_pyproject_toml()
            self.path_layout.copy_file(
                p_src=self.path_layout.dir_project_root / "uv.lock",
                p_dst=self.path_layout.dir_repo / "uv.lock",
            )

        def step_3_execute_build(self):
            super().step_3_execute_build()
            dir_repo = self.path_layout.dir_repo
            uv = str(self.path_bin_uv or "uv")
            subprocess.run(
                [uv, "venv", str(dir_repo / ".venv")],
                cwd=str(dir_repo), check=True,
            )
            subprocess.run(
                [uv, "pip", "install", "-r", "pyproject.toml",
                 "--python", str(dir_repo / ".venv" / "bin" / "python")],
                cwd=str(dir_repo), check=True,
            )

        def step_4_finalize_artifacts(self):
            super().step_4_finalize_artifacts()
            move_to_dir_python(
                dir_site_packages=self.path_layout.dir_build_lambda_layer_repo_venv_site_packages,
                dir_python=self.path_layout.dir_python,
            )


End-to-End Workflow
------------------------------------------------------------------------------

With the builder implemented, use
:class:`~aws_lbd_art_builder_core.layer.workflow.LayerDeploymentWorkflow`
to run the full pipeline in one call:

.. code-block:: python

    from pathlib import Path
    from s3pathlib import S3Path
    from aws_lbd_art_builder_core.layer.api import LayerDeploymentWorkflow

    # Create a tool-specific builder (satisfies T_BUILDER protocol)
    builder = UvLambdaLayerLocalBuilder(
        path_pyproject_toml=Path("pyproject.toml"),
        skip_prompt=True,
    )

    # Run the full Build → Package → Upload → Publish pipeline
    workflow = LayerDeploymentWorkflow(
        builder=builder,
        path_manifest=Path("uv.lock"),
        s3dir_lambda=S3Path("s3://my-bucket/projects/my_app/lambda/"),
        layer_name="my_app",
        s3_client=s3_client,
        lambda_client=lambda_client,
        publish_layer_version_kwargs={
            "CompatibleRuntimes": ["python3.12"],
            "Description": "my_app dependencies layer",
        },
    )
    deployment = workflow.run()
    # deployment.layer_version, deployment.layer_version_arn, ...

You can also call individual steps if you need finer control:

.. code-block:: python

    workflow.step_1_build()
    workflow.step_2_package()
    workflow.step_3_upload()
    deployment = workflow.step_4_publish()

.. note::

    ``path_manifest`` is always the **tool-specific lock/requirements file**:
    ``uv.lock`` for uv, ``poetry.lock`` for poetry, ``requirements.txt`` for pip.
    Core never interprets its contents — it only hashes and stores it for
    change detection.


Container Builds
------------------------------------------------------------------------------

For cross-platform compatibility (C extensions, etc.), sub-packages can also
subclass :class:`~aws_lbd_art_builder_core.layer.builder.BaseLambdaLayerContainerBuilder`.

The container builder runs a Python script inside an official AWS SAM Docker
image. The sub-package provides ``path_script`` — the build script that
runs inside the container:

.. code-block:: python

    @dataclasses.dataclass(frozen=True)
    class UvLambdaLayerContainerBuilder(BaseLambdaLayerContainerBuilder):
        """Build a Lambda layer using uv inside a Docker container."""
        pass  # base class handles everything; just supply path_script

The build script (a standalone ``.py`` file) runs inside Docker with the
project root mounted at ``/var/task``. It should install dependencies into
the layer build directory. See
:attr:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout.get_path_in_container`
for path translation.


Key Design Decisions for Sub-Package Authors
------------------------------------------------------------------------------

**Manifest file**: Each tool has one canonical manifest that represents the full
dependency state. Pass it as ``path_manifest`` to ``upload_layer_zip_to_s3``
and ``LambdaLayerVersionPublisher``. The publisher uses it for change detection
(skip publish if manifest hasn't changed since last version).

**Why Command Pattern**: All builder parameters are dataclass fields, not
function arguments. This means sub-packages can add new fields (e.g.
``path_bin_uv``) without changing the ``run()`` signature. The frozen
dataclass also makes builders inspectable and reproducible.

**Don't duplicate core logic**: Never re-implement zipping, uploading, or
publishing in a sub-package. These are deliberately centralized in core so
that bug fixes and improvements propagate to all tools automatically.

**Credentials**: Core provides ``Credentials.poetry_login()``,
``Credentials.uv_login()``, and ``Credentials.pip_extra_index_url`` for
private repo authentication. Use these in your ``step_3_execute_build``
rather than reimplementing auth logic.
