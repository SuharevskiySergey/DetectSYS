"""Standalone regression runner: deterministic half-suite by default, --full for all."""
import argparse
from pathlib import Path
import sys
import unittest


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Run all regressions instead of the fast half-suite')
    parser.add_argument('--list', action='store_true', help='Print selected test IDs without running them')
    args = parser.parse_args()
    loader = unittest.TestLoader()
    suite = loader.discover(str(Path(__file__).resolve().parent), pattern='test_*.py')
    # Discovery failures must never disappear through half-suite selection.
    if loader.errors:
        for error in loader.errors:
            print(error, file=sys.stderr)
        return 1
    tests = sorted(flatten(suite), key=lambda test: test.id())
    selected = tests if args.full else tests[::2]
    print(f'{"Full" if args.full else "Fast"} suite: {len(selected)}/{len(tests)} tests', file=sys.stderr, flush=True)
    if not selected:
        print('No tests discovered', file=sys.stderr)
        return 1
    if args.list:
        for test in selected:
            print(test.id())
        return 0
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(selected))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
