#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#


import sys

from airbyte_cdk.entrypoint import launch
from source_thelessonspace import SourceTheLessonSpace

if __name__ == "__main__":
    source = SourceTheLessonSpace()
    launch(source, sys.argv[1:])
