#!/usr/bin/env python

from __future__ import print_function

import argparse
import os
import sys
import time

from buildfarm.status_page import bin_arches, get_distro_arches, render_csv, ros_repos, transform_csv_to_html
from rosrpm.core import fedora_release_version

def parse_options(args=sys.argv[1:]):
    p = argparse.ArgumentParser(description='Generate the HTML page showing the package build status.')
    p.add_argument('--basedir', default='/tmp/build_status_page', help='Root directory containing ROS apt caches. This should be created using the build_caches command.')
    p.add_argument('--skip-csv', action='store_true', help='Skip generating .csv file.')
    p.add_argument('rosdistro', default='groovy', help='The ROS distro to generate the status page for (i.e. groovy).')
    return p.parse_args(args)


if __name__ == '__main__':
    args = parse_options()

    start_time = time.localtime()

    csv_file = os.path.join(args.basedir, '%s.csv' % args.rosdistro)
    if not args.skip_csv:
        print('Generating .csv file...')
        render_csv(csv_file, args.rosdistro)
    elif not os.path.exists(csv_file):
        print('.csv file "%s" is missing. Call script without "--skip-csv".' % csv_file, file=sys.stderr)
    else:
        print('Skip generating .csv file')

    def metadata_builder(column_data):
        distro, jobtype = column_data.split('_', 1)
        data = {
            'rosdistro': args.rosdistro,
            'rosdistro_short': args.rosdistro[0].upper(),
            'distro': distro,
            'distro_short': distro[0].upper(),
            'distro_ver': fedora_release_version(distro)
        }
        is_source = jobtype == 'SRPMS'
        if is_source:
            column_label = '{rosdistro_short}src{distro_short}'
            view_name = '{rosdistro_short}src'
        else:
            data['arch_short'] = {'x86_64': '64', 'i386': '32'}[jobtype]
            column_label = '{rosdistro_short}binF{distro_ver}x{arch_short}'
            view_name = '{rosdistro_short}binF{distro_ver}x{arch_short}'
        data['column_label'] = column_label.format(**data)
        data['view_url'] = 'http://151.159.91.137:8080/view/%s/' % view_name.format(**data)

        if is_source:
            job_name = 'ros-{rosdistro}-{{pkg}}_sourcerpm'
        else:
            data['arch'] = jobtype
            job_name = 'ros-{rosdistro}-{{pkg}}_binaryrpm_{distro}_{arch}'
        data['job_url'] = ('{view_url}job/%s/' % job_name).format(**data)

        return data

    print('Transforming .csv into .html file...')
    with open(csv_file, 'r') as f:
        html = transform_csv_to_html(f, metadata_builder, args.rosdistro, start_time)
    html_file = os.path.join(args.basedir, '%s.html' % args.rosdistro)
    with open(html_file, 'w') as f:
        f.write(html)

    print('Symlinking jQuery resources...')
    dst = os.path.join(args.basedir, 'jquery')
    if not os.path.exists(dst):
        src = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'jquery')
        os.symlink(src, dst)

    print('Generated .html file "%s"' % html_file)
