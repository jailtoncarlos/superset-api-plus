#!/usr/bin/python3

import os
import shlex
import sys
import subprocess


def get_changed_files():
    process = subprocess.Popen(shlex.split('git diff --name-only origin/master..'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
    files = []
    for line in iter(process.stdout.readline, b''):
        output = line.rstrip().decode()
        if output.endswith('.py'):
            files.append(output)
    return files


def main():
    if '--all' in sys.argv:
        apps = '.'
        if '-v' in sys.argv or '--verbose' in sys.argv:
            sys.stdout.write('>>> All files will be evaluated\n')
    else:
        files = get_changed_files()
        apps = ' '.join(file for file in files if os.path.exists(file))
        if '-v' in sys.argv or '--verbose' in sys.argv:
            sys.stdout.write('>>> The following files will be evaluated:\n')
            sys.stdout.write('\n'.join(files))
            sys.stdout.write('\n')

    if apps:
        result = os.system(f'autopep8 -r --ignore E501 -i --exit-code {apps}')
        if result:
            sys.stderr.write('Formatting carried out\n')
            sys.exit(1)
        else:
            sys.stdout.write('>>>>>> No formatting done...\n')
    else:
        sys.stdout.write('>>>>>> No formatting done...\n')


if __name__ == '__main__':
    main()
