#!/usr/bin/env python3
"""Helper to find files modified by multiple commits.

Some files have a number of cleanup or refactoring commits applied to
them. To make the history a little cleaner to aid with cherry-picking
to a new version, find files with multiple commits and list
them. (Sometimes multiple commits are fine when they are completely
distinct, the goal here is just to squash cleanup/refactoring
commits.)

Example usage:

./files_with_multiple_commits.py /my/git/repo my-branch v1.2.4
"""

import argparse
import subprocess


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('repo', help='repo path')
    parser.add_argument('modified_rev', help='modified revision')
    parser.add_argument('upstream_rev', help='upstream revision')
    parser.add_argument(
        'ignore_paths',
        nargs='*',
        help='paths of files that should be excluded from the output')
    return parser.parse_args()


def main():
    """Helper to find files modified by multiple commits."""
    args = parse_args()

    # Use git-cherry to find a list of the commits we are interested in
    cmd = ('git', '-C', args.repo, 'cherry', args.upstream_rev,
           args.modified_rev)
    output = subprocess.run(cmd, capture_output=True, check=True, text=True)
    commits = []
    for line in output.stdout.splitlines():
        # Each line looks like this:
        #
        # + e7d7606021c3e80024996a32793b98541368f2b3
        commits.append(line.split()[1])

    # Map of modified paths to a list of commits that modified that path
    modified_paths = {}
    # Map from commit hash to commit messages
    commit_messages = {}

    for commit in commits:
        # Get the list of paths modified by the commit. The output
        # looks like this:
        #
        # drm/i915: add suspend quirk for the Lenovo Thinkpad SL410
        # drivers/gpu/drm/i915/i915_drv.c
        cmd = ('git', '-C', args.repo, 'show', '--name-only',
               '--pretty=format:%s', commit)
        output = subprocess.run(cmd,
                                capture_output=True,
                                check=True,
                                text=True)

        # The first line of the output is the first line of the commit
        # message
        lines = output.stdout.splitlines()
        commit_messages[commit] = lines[0]

        for path in lines[1:]:
            # Skip paths listed on the command line
            if path in args.ignore_paths:
                continue

            if path in modified_paths:
                modified_paths[path].append(commit)
            else:
                modified_paths[path] = [commit]

    for path, commits in modified_paths.items():
        # Only show paths modified by more than one commit
        if len(commits) > 1:
            print(path)
            for commit in commits:
                print('  {} {}'.format(commit[:10], commit_messages[commit]))


if __name__ == '__main__':
    main()
