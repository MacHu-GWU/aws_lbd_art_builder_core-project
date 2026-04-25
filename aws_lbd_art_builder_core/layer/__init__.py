# -*- coding: utf-8 -*-

"""
AWS Lambda layer creation and deployment package.

This package provides a complete 4-step workflow for creating, packaging, and deploying
AWS Lambda layers with dependencies from Python package managers. It supports multiple
dependency management tools and both local and containerized builds for cross-platform
compatibility.

**Complete Layer Workflow:**

1. **Build** - Install and resolve dependencies using pip, Poetry, or UV
2. **Package** - Structure and compress dependencies into deployable artifacts
   - :mod:`package`: Transform build output into Lambda-compatible zip files
3. **Upload** - Deploy layer artifacts to S3 storage for Lambda access
4. **Publish** - Create versioned Lambda layer from stored artifacts
"""
