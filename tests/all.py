# -*- coding: utf-8 -*-

if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core",
        is_folder=True,
        preview=False,
    )
