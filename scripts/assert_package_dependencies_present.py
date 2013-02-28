#!/usr/bin/env python

import os
import argparse
import sys
import subprocess
import shutil
import tempfile
import yaml

from rosrpm.repo import load_Packages

def parse_options():
    parser = argparse.ArgumentParser(description="Return 0 if all packages are found in the repository, else print missing packages and return 1.")
    parser.add_argument(dest="repo_url",
                        help='repository to query for package(s)')
    parser.add_argument(dest="distro",
                        help='Fedora distribution of target repository (eg \'spherical\' or \'beefy\')')
    parser.add_argument(dest="packages", nargs='+',
                        help="what packages to test for.")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_options()

    pkgs = {
        'SRPMS':load_Packages(args.repo_url, args.distro, 'SRPMS'),
        'i386':load_Packages(args.repo_url, args.distro, 'i386'),
        'x86_64':load_Packages(args.repo_url, args.distro, 'x86_64')
    }
    missing = []
    for p in args.packages:
        try:
            srpm = [r for r in pkgs['SRPMS'] if r[0] == p]
            if not srpm:
                missing.append(p)
                print "No SRPM file found for package %s"%p
            else:
                for dep in srpm[0][2]:
                    dep_name_only = dep.split()[0]
                    dep_srpm = [r for r in pkgs['SRPMS'] if r[0] == dep_name_only]
                    if not dep_srpm:
                        print "package %s does not have dependency [%s]"%(p, dep_name_only)
                        missing.append(dep_name_only)

        except Exception, ex:
            print "Exception processing package %s: %s"%(p, ex)
            missing.append(p)

    if missing:
        print "Dependencies not satisfied for packages: %s"%missing
        sys.exit(1)
    else:
        sys.exit(0)
