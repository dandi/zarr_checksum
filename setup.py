#!/usr/bin/env python

import setuptools

if __name__ == "__main__":
    setuptools.setup(
        entry_points={
            "console_scripts": [
                "zarrsum=zarrsum.cli:cli",
            ]
        }
    )
