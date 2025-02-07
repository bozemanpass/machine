# Exposing the truth that dependency injection is just a fancy name for global variables

from machine.types import CliOptions


class d:
    opt: CliOptions = None
