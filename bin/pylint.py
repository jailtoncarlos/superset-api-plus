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
    if not apps:
        apps = '.'

    result = subprocess.run(f'flake8 {apps} --ignore E501,W503,W291,E713,E712,E902 --exclude src/'.split(' '), capture_output=True)
    stdout = result.stdout.decode('utf-8')
    ok = len(stdout)
    if ok > 0:
        sys.stderr.write(stdout)
        sys.stderr.write('\nCorrect the errors! :)\n')
        sys.exit(1)
    else:
        print('>>>>>> No warnings found...')


if __name__ == '__main__':
    main()
