from __future__ import annotations

import argparse
import ast
import traceback
import tokenize
from typing import Sequence

FILENAMES = (
    '*.py'
)


def check_file(filename: str) -> int:
    try:
        with open(filename, 'rb') as f:
            ast.parse(f.read(), filename=filename)
    except SyntaxError:
        print(f'{filename} - Could not parse ast')
        print()
        print('\t' + traceback.format_exc().replace('\n', '\n\t'))
        print()
        return 1

    lines = []
    with tokenize.open(filename) as f:
        tokens = tokenize.generate_tokens(f.readline)
        line = None
        for token in tokens:
            # next token after finding statement
            # should come before the line should be changed
            if line:
                # if comment found at the same line, ignore statement
                if token.start[0] == line.start[0] and token.type == 61 and token.string == '# NOQA':
                    line = None
                    continue

                # next line from import with no previous comment
                if token.start[0] > line.start[0]:
                    lines.append(line)
                    line = None
                    continue
            # statement found
            if token.string == 'print' and token.type == 1:
                line = token
                continue

    for line in lines:
        print(f'{filename}:{line.start[0]}:{line.start[1]}: {line.string} found')

    return int(bool(lines))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='Filenames to run')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for pattern in FILENAMES:
            if filename.endswith(pattern):
                retv |= check_file(filename)
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
