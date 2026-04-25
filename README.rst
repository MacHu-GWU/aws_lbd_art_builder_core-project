
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
- **N tool-specific packages** (``aws_lbd_art_builder_uv``, ``aws_lbd_art_builder_pip``, ``aws_lbd_art_builder_poetry``): each implements Step 1 (dependency installation) and wires the full 4-step Lambda layer workflow.

Core never calls ``pip install``, ``uv sync``, or ``poetry install`` directly — those belong exclusively in the tool-specific sub-packages.


.. _install:

Install
------------------------------------------------------------------------------

``aws_lbd_art_builder_core`` is released on PyPI, so all you need is to:

.. code-block:: console

    $ pip install aws-lbd-art-builder-core

To upgrade to latest version:

.. code-block:: console

    $ pip install --upgrade aws-lbd-art-builder-core
