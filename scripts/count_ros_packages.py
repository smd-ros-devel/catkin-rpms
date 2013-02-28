#!/usr/bin/env python

import argparse
import rosrpm.repo
import sys

def parse_options():
    parser = argparse.ArgumentParser(description="List all packages available in the repos for each arch.  Filter on substring if provided")
    parser.add_argument("rosdistro",
           help='The ros distro. electric, fuerte, groovy')
    parser.add_argument("distro",
           help='Fedora distro beefy, spherical, etc')
    parser.add_argument("arch",
           help='The arch x86_64 i386')
    parser.add_argument('--repo', dest='repo_url', action='store', default='http://csc.mcs.sdsmt.edu/smd-ros-building',
           help='The repo url')

    parser.add_argument('--count', dest='count', action='store', default=100,
           help='Min numberof packages')

    args = parser.parse_args()


    return args


if __name__ == "__main__":
    args = parse_options()



    count = rosrpm.repo.count_packages(args.repo_url, args.rosdistro, args.distro, args.arch)
    print "Found %d packages matching: %s" % (count, args)

    min_num = int(args.count)
    if count > min_num:
        print "Count greater than argument, return True"
        sys.exit(0)
    else:
        print "Count not greater than argument, return False"
        sys.exit(1)
