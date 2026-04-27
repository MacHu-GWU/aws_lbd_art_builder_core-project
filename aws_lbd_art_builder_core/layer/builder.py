# -*- coding: utf-8 -*-

"""
Base command classes for Lambda layer building — Step 1 of the layer workflow.

**Why Command Pattern?**

Layer builds have many configuration knobs (paths, credentials, Python version,
architecture, Docker options, …). A plain function would accumulate these as
positional/keyword arguments; every subclass or wrapper that adds a knob must
change the function signature, which ripples through all callers.

With the Command Pattern each knob is a dataclass field on the instance.
Subclasses add fields freely without touching ``run()``'s signature (always
zero-arg). Callers construct → optionally override steps → call ``run()``.

This module provides two abstract bases:

- :class:`BaseLambdaLayerLocalBuilder` — builds directly on the host
- :class:`BaseLambdaLayerContainerBuilder` — builds inside a Docker container

Both follow a standardized 4-step workflow. Downstream packages (e.g.
``aws_lbd_art_builder_uv``) subclass and implement the tool-specific steps.
"""

import dataclasses
from pathlib import Path
from functools import cached_property

from func_args.api import REQ

from .foundation import LayerPathLayout
from .foundation import BaseLogger


@dataclasses.dataclass(frozen=True)
class BaseLambdaLayerContainerBuilder(BaseLogger):
    """
    Base command class for containerized Lambda layer builds.

    Uses official AWS SAM Docker images to ensure the built layer matches the
    Lambda runtime environment exactly. This is important for packages with
    C extensions that must be compiled for the target architecture.

    **Usage**: Subclass and provide a tool-specific build script via
    :attr:`path_script`. Call :meth:`run` to execute containerized build,
    or customize individual steps as needed.
    """

    path_pyproject_toml: Path = dataclasses.field(default=REQ)
    py_ver_major: int = dataclasses.field(default=REQ)
    py_ver_minor: int = dataclasses.field(default=REQ)
    is_arm: bool = dataclasses.field(default=REQ)

    @cached_property
    def path_layout(self) -> LayerPathLayout:
        """
        :class:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout`
        object for managing build paths.
        """
        return LayerPathLayout(
            path_pyproject_toml=self.path_pyproject_toml,
        )

    @property
    def image_tag(self) -> str:
        """
        Docker image tag based on target architecture.

        :return: Architecture-specific tag for AWS SAM build images
        """
        if self.is_arm:
            return "latest-arm64"
        else:
            return "latest-x86_64"

    @property
    def image_uri(self) -> str:
        """
        Full Docker image URI for AWS SAM build container.

        :return: Complete Docker image URI from AWS public ECR
        """
        return (
            f"public.ecr.aws/sam"
            f"/build-python{self.py_ver_major}.{self.py_ver_minor}"
            f":{self.image_tag}"
        )

    @property
    def platform(self) -> str:
        """
        Docker platform specification for target architecture.

        :return: Platform string for docker run --platform argument
        """
        if self.is_arm:
            return "linux/arm64"
        else:
            return "linux/amd64"

    @property
    def container_name(self) -> str:
        """
        Unique container name for the build process.

        :return: Descriptive container name for docker run --name argument
        """
        suffix = "arm64" if self.is_arm else "amd64"
        return (
            f"lambda_layer_builder"
            f"-python{self.py_ver_major}{self.py_ver_minor}"
            f"-{suffix}"
        )

    @property
    def docker_run_args(self) -> list[str]:
        """
        Complete Docker run command arguments.

        :return: List of command arguments for subprocess execution
        """
        return [
            "docker",
            "run",
            "--rm",  # Auto-remove container when done
            "--name",
            self.container_name,
            "--platform",
            self.platform,
            "--mount",
            f"type=bind,source={self.path_layout.dir_build_lambda_layer},target=/var/task",
            self.image_uri,
            "python",
            "-u",  # Unbuffered output for real-time logging
            self.path_layout.path_build_lambda_layer_in_container_script_in_container,
        ]
