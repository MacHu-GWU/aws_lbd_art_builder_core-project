# -*- coding: utf-8 -*-

"""
AWS Lambda layer creation and deployment package.

This package provides the tool-agnostic parts of the 4-step workflow for
creating, packaging, and deploying AWS Lambda layers. Step 1 (installing
dependencies with pip, Poetry, or uv) is implemented by downstream packages
such as ``aws_lbd_art_builder_uv``.

**Complete Layer Workflow:**

1. **Build** - Install dependencies (downstream builder; core provides
   :mod:`foundation` paths and the :mod:`builder` container base class)
2. **Package** - :mod:`package`: compress ``python/`` into ``layer.zip``
3. **Upload** - :mod:`upload`: upload ``layer.zip`` to an S3 staging location
4. **Publish** - :mod:`publish`: create a versioned Lambda layer from it

:mod:`workflow` runs all four steps with any builder.
"""
