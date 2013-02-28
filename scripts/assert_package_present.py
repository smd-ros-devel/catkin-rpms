#!/usr/bin/env python

import os
import argparse
import sys
import subprocess
import shutil
import tempfile
import yaml

from rosrpm.repo import rpm_in_repo

def parse_options():
    parser = argparse.ArgumentParser(description="Return 0 if all packages are found in the repository, else print missing packages and return 1.")
    parser.add_argument(dest="repo_url",
                        help='repository to query for package(s)')
    parser.add_argument(dest="distro",
                        help='Fedora distribution of target repository (eg \'spherical\' or \'beefy\')')
    parser.add_argument(dest="arch",
                        help='Architecture of target repository (eg \'i386\' or \'x86_64\')')
    parser.add_argument(dest="packages", nargs='+',
                        help="what packages to test for.")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_options()

    for p in args.packages:
        failure = False
        if not rpm_in_repo(args.repo_url, p, '.*', args.distro, args.arch):
            print "Package %s missing in repo." %p
            failure = True

    if failure:
        sys.exit(1)
    sys.exit(0)
