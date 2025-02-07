import sys


def fatal_error(s: str):
    print(s, file=sys.stderr)
    sys.exit(1)


def debug(s: str):
    print(s, file=sys.stderr)


def info(s: str):
    print(s, file=sys.stderr)


def output(s: str):
    print(s)
