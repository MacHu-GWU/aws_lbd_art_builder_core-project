# -*- coding: utf-8 -*-

import s3pathlib


def lambda_handler(event, context):
    print(f"{s3pathlib.__version__ = }")
