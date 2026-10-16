
.. image:: https://readthedocs.org/projects/aws-lbd-art-builder-core/badge/?version=latest
    :target: https://aws-lbd-art-builder-core.readthedocs.io/en/latest/
    :alt: Documentation Status

.. image:: https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project/actions/workflows/main.yml/badge.svg
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project/actions?query=workflow:CI

.. image:: https://codecov.io/gh/MacHu-GWU/aws_lbd_art_builder_core-project/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/MacHu-GWU/aws_lbd_art_builder_core-project

.. image:: https://img.shields.io/pypi/v/aws-lbd-art-builder-core.svg
    :target: https://pypi.python.org/pypi/aws-lbd-art-builder-core

.. image:: https://img.shields.io/pypi/l/aws-lbd-art-builder-core.svg
    :target: https://pypi.python.org/pypi/aws-lbd-art-builder-core

.. image:: https://img.shields.io/pypi/pyversions/aws-lbd-art-builder-core.svg
    :target: https://pypi.python.org/pypi/aws-lbd-art-builder-core

.. image:: https://img.shields.io/badge/✍️_Release_History!--None.svg?style=social&logo=github
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project/blob/main/release-history.rst

.. image:: https://img.shields.io/badge/⭐_Star_me_on_GitHub!--None.svg?style=social&logo=github
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project

------

.. image:: https://img.shields.io/badge/Link-API-blue.svg
    :target: https://aws-lbd-art-builder-core.readthedocs.io/en/latest/py-modindex.html

.. image:: https://img.shields.io/badge/Link-Install-blue.svg
    :target: `install`_

.. image:: https://img.shields.io/badge/Link-GitHub-blue.svg
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project

.. image:: https://img.shields.io/badge/Link-Submit_Issue-blue.svg
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project/issues

.. image:: https://img.shields.io/badge/Link-Request_Feature-blue.svg
    :target: https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project/issues

.. image:: https://img.shields.io/badge/Link-Download-blue.svg
    :target: https://pypi.org/pypi/aws-lbd-art-builder-core#files


Welcome to ``aws_lbd_art_builder_core`` Documentation
==============================================================================
.. image:: https://aws-lbd-art-builder-core.readthedocs.io/en/latest/_static/aws_lbd_art_builder_core-logo.png
    :target: https://aws-lbd-art-builder-core.readthedocs.io/en/latest/

``aws_lbd_art_builder_core`` is the **shared base** in a family of AWS Lambda artifact builder packages. It follows a **1+N design**:

- **1 core package** (this one): tool-agnostic infrastructure — path layouts, S3 layouts, credentials, layer packaging, upload, publish, and Lambda source artifact build.
- **N tool-specific packages**, such as `aws_lbd_art_builder_uv <https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project>`_: each one installs a Lambda layer's dependencies with its tool (Step 1) and hands the result to core.

It covers two jobs:

- **Lambda layer**: Build (sub-package) → Package ``layer.zip`` → Upload to S3 → Publish a new layer version. Core publishes only when the dependency lock file changed since the last published version, so unchanged dependencies never create a new version. ``LayerDeploymentWorkflow`` runs all four steps in one call.
- **Lambda function source**: install your project (without its dependencies) with ``pip`` or ``uv``, zip it, and upload it to ``s3://.../source/{version}/{sha256}/source.zip``. The SHA256 in the key makes CDK / CloudFormation redeploy whenever the code changes.

Core never calls ``uv sync``, ``poetry install``, or ``pip install -r`` to install layer dependencies; those belong to the tool-specific sub-packages. Most users install a sub-package, which pulls in core.

.. tip::

    This repo ships two Claude Code agent skills in ``.claude/skills/``:

    - ``pypi-aws_lbd_art_builder_core``: the public API, for coding agents that **use** this library. Copy the folder into the ``.claude/skills/`` of the project that depends on it.
    - ``maintain-aws_lbd_art_builder_core``: how the code works inside, for coding agents that **change** this repo. It is available automatically when you work in this repo.


Quick Look
------------------------------------------------------------------------------
Build and upload a Lambda function's source code:

.. code-block:: python

    import shutil
    from pathlib import Path

    import boto3
    from s3pathlib.api import S3Path
    from aws_lbd_art_builder_core.api import source_api

    s3_client = boto3.Session().client("s3")
    s3dir_lambda = S3Path("s3://my-bucket/projects/my_app/lambda/")

    result = source_api.build_and_upload_source_using_uv(
        s3_client=s3_client,
        path_bin_uv=Path(shutil.which("uv")),
        dir_project_root=Path("/path/to/my_app-project"),
        s3dir_source=source_api.SourceS3Layout.from_s3dir_lambda(s3dir_lambda).dir_root,
        skip_prompt=True,
    )
    print(result.s3path_source_zip.uri)

Build and publish a Lambda layer, with a builder from a sub-package:

.. code-block:: python

    import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv
    from aws_lbd_art_builder_core.api import layer_api

    boto_ses = boto3.Session()
    workflow = layer_api.LayerDeploymentWorkflow(
        builder=aws_lbd_art_builder_uv.layer_api.UvLambdaLayerLocalBuilder(
            path_pyproject_toml=Path("/path/to/my_app-project/pyproject.toml"),
            skip_prompt=True,
        ),
        path_manifest=Path("/path/to/my_app-project/uv.lock"),
        s3dir_lambda=s3dir_lambda,
        layer_name="my_app",
        s3_client=boto_ses.client("s3"),
        lambda_client=boto_ses.client("lambda"),
    )
    deployment = workflow.run()  # raises ValueError if uv.lock is unchanged
    print(deployment.layer_version_arn)

Pass plain boto3 clients. S3 locations are ``s3pathlib`` 3.x ``S3Path`` objects.


.. _install:

Install
------------------------------------------------------------------------------

``aws_lbd_art_builder_core`` is released on PyPI and supports Python 3.11 to 3.14. The base install only covers paths, zipping, and helpers; the AWS steps need an extra:

.. code-block:: console

    $ pip install "aws-lbd-art-builder-core[upload]"     # S3 upload (boto3, s3pathlib 3.x)
    $ pip install "aws-lbd-art-builder-core[publish]"    # upload + publish Lambda layer versions

To upgrade to latest version:

.. code-block:: console

    $ pip install --upgrade "aws-lbd-art-builder-core[publish]"

Upgrading from 0.x: 1.0.0 moved to ``s3pathlib`` 3.x and no longer accepts a ``BotoSesManager`` as ``s3_client``; see the `release history <https://github.com/MacHu-GWU/aws_lbd_art_builder_core-project/blob/main/release-history.rst>`_.
