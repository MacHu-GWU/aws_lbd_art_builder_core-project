# -*- coding: utf-8 -*-

from soft_deps.api import MissingDependency

try:
    from s3pathlib import S3Path
except ImportError as e:  # pragma: no cover
    S3Path = MissingDependency(
        name="s3pathlib",
        error_message="please do 'pip install aws_lbd_art_builder_core[upload]'",
    )

try:  # pragma: no cover
    import simple_aws_lambda.api as simple_aws_lambda
except ImportError as e:
    simple_aws_lambda = MissingDependency(
        name="simple_aws_lambda",
        error_message="please do 'pip install aws_lbd_art_builder_core[publish]'",
    )
