#!/usr/bin/env python3
"""Alternate form of rebasing using cherry picks.

Example scenario:

Let's say there's an upstream repo called Base. You create a fork of
Base. Perhaps Base has a master or main branch, but your fork is based
off a version tag such as v1.2.3. You make changes to your branch fork
and occasionally pull in patch changes from upstream, e.g. `git merge
v1.2.4`.

Eventually the time comes that you want to move your changes to a
newer version of Base, say v2.0.0. If enough time has passed your
forked branch may have a complicated history of internal merges and
merges from upstream. You don't want to just merge v2.0.0 into your
branch, because there might be fixes from the v1.2 patch versions that
don't belong in the v2 branch.

One solution is to rebase all the changes in your branch onto the old
upstream version (e.g. v1.2.4), then cherry-pick those changes over to
a new branch based on v2.0.0. But a sufficiently complicated history
can make this complicated; you may run into conflicts on almost every
step of the rebase.

This script presents an alternative: get the diff between your branch
and the old upstream version, then use `git blame` to find the commit
that last touched each line. Deduplicate all the commits then sort
them from oldest to newest. Finally all the commits are cherry-picked
to a detached checkout of the old upstream version. This is a
multi-commit cherry-pick, so if any commit has conflicts you will need
to resolve it then run `git cherry-pick --continue` to move on to the
next commit.

Once you've finished the cherry-pick, you should `git diff` against
the original branch to see if anything was accidentally changed. Note
in particular that the current method of using `git blame` does not
handle deleted lines, so a patch that only removed lines without
adding or changing any lines will be missed.

Once all this has been done you can do additional cleanups of the
commits via rebase, then cherry-pick the final commits to a new branch
based on the new upstream version you are transitioning to.

Example usage:

./once_again.py /my/git/repo my-branch v1.2.4
"""

import argparse
import subprocess

import whatthepatch


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('repo', help='repo path')
    parser.add_argument('modified_rev', help='modified revision')
    parser.add_argument('upstream_rev', help='upstream revision')
    return parser.parse_args()


def get_commits_from_patch(patch, args):
    """Get the set of commits associated with added lines in the patch."""
    commits = set()

    for diff in whatthepatch.parse_patch(patch):
        for change in diff.changes:
            # Ignore lines that aren't insertions
            if change.old is not None or change.new is None:
                continue

            cmd = ('git', '-C', args.repo, 'blame',
                   '-L{0},{0}'.format(change.new), args.modified_rev,
                   diff.header.new_path)
            output = subprocess.run(cmd,
                                    capture_output=True,
                                    check=True,
                                    text=True)
            # Output looks like this:
            #
            # f9aa76a852485 (Dave Airlie 2012-04-17 14:12:29 +0100 132) 	.name = DRIVER_NAME,
            #
            # Discard everything from the first close paren on, then
            # get the commit hash and the data portion of the
            # output. (I'm not sure whether this is author date or
            # commit date.)
            header = output.stdout.split(')')[0]
            parts = header.split()
            commit_hash = parts[0]
            commit_date = parts[-4]
            commit_time = parts[-3]
            commit_zone = parts[-2]

            commit_datetime = '{}T{}{}'.format(commit_date, commit_time,
                                               commit_zone)
            commits.add((commit_datetime, commit_hash))

    return commits


def main():
    """Alternate form of rebasing using cherry picks.

    1. Use `git diff` to find the differences from the upstream commit
    to the forked commit.

    2. Use whatthepatch to parse the diff. For each line that is an
    insertion in the diff, use `git blame` to find the commit that
    last touched that line. (Finding the commit that removed a line is
    doable but trickier; I didn't bother doing it since very few
    commits are *only* removing lines, and those can be cherry-picked
    manually later.)

    3. Deduplicate all the commits found in step two and sort them
    from oldest to newest.

    4. Create a detached checkout of the upstream commit and
    cherry-pick all the commits from oldest to newest.

    """
    args = parse_args()

    cmd = ('git', '-C', args.repo, 'diff', args.upstream_rev,
           args.modified_rev)
    output = subprocess.run(cmd, capture_output=True, check=True, text=True)
    patch = output.stdout

    commits = get_commits_from_patch(patch, args)

    # Checkout the detached upstream revision in preparation for
    # cherry picking
    cmd = ('git', '-C', args.repo, 'checkout', '--detach', args.upstream_rev)
    print(' '.join(cmd))
    subprocess.run(cmd, check=True)

    # Get the commit hashes from oldest to newest
    sorted_commits = [commit for _, commit in sorted(commits)]

    # Cherry pick all the commits from oldest to newest
    cmd = ['git', '-C', args.repo, 'cherry-pick'] + sorted_commits
    print(' '.join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == '__main__':
    main()
