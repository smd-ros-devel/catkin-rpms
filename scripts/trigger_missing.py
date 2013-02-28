#!/usr/bin/env python

from __future__ import print_function

import argparse
import jenkins
import pprint

from buildfarm import jenkins_support, release_jobs
from buildfarm.rosdistro import redhatify_package_name


def parse_options():
    parser = argparse.ArgumentParser(
             description='Create a set of jenkins jobs '
             'for source RPMs and binary RPMs for a catkin package.')
    parser.add_argument('--fqdn', dest='fqdn',
           help='The source repo to push to, fully qualified domain name',
           default='csc.mcs.sdsmt.edu')
    parser.add_argument(dest='rosdistro',
           help='The ros distro. electric, fuerte, groovy')
    parser.add_argument('--distros', nargs='+',
           help='A list of Red Hat distros. Default: %(default)s',
           default=[])
    parser.add_argument('--arches', nargs='+',
           help='A list of Red Hat arches. Default: %(default)s',
           default=['i386','x86_64'])
    parser.add_argument('--sourcerpm-only', action='store_true', default=False,
           help='Only check sourcerpm jobs. Default: all')
    parser.add_argument('--wet-only', action='store_true', default=False,
           help='Only check wet package jobs. Default: all')
    parser.add_argument('--commit', dest='commit',
           help='Really?', action='store_true')
    return parser.parse_args()


def trigger_if_necessary(da, pkg, rosdistro, jenkins_instance, missing_by_arch):
    if da[1] != 'SRPMS' and da in missing_by_arch and pkg in missing_by_arch[(da[0], 'SRPMS')]:
        print ("  Skipping trigger of binaryrpm job for package '%s' on arch '%s' as the sourcerpm job will trigger them automatically" % (pkg, '_'.join(da)))
        return False

    if da[1] == 'SRPMS':
        job_name = '%s_sourcerpm_%s' % (redhatify_package_name(rosdistro, pkg), da[0])
    else:
        job_name = '%s_binaryrpm_%s' % (redhatify_package_name(rosdistro, pkg), '_'.join(da))
    job_info = jenkins_instance.get_job_info(job_name)

    if 'color' in job_info and 'anime' in job_info['color']:
        print ("  Skipping trigger of job %s because it's already running" % job_name)
        return False

    if 'inQueue' in job_info and job_info['inQueue']:
        print ("  Skipping trigger of job '%s' because it's already queued" % job_name)
        return False

    if da[1] != 'SRPMS' and 'upstreamProjects' in job_info:
        upstream = job_info['upstreamProjects']
        for p in missing_by_arch[da]:
            p_name = '%s_binaryrpm_%s' % (redhatify_package_name(rosdistro, p), '_'.join(da))
            for u in upstream:
                if u['name'] == p_name:
                    print ("  Skipping trigger of job '%s' because the upstream job '%s' is also triggered" % (job_name, p_name))
                    return False

    print ("Triggering '%s'" % (job_name))
    #return jenkins_instance.build_job(job_name)
    # replicate internal implementation of Jenkins.build_job()
    import urllib2
    if not jenkins_instance.job_exists(job_name):
        raise jenkins.JenkinsException('no such job[%s]' % (job_name))
    # pass parameters to create a POST request instead of GET
    return jenkins_instance.jenkins_open(urllib2.Request(jenkins_instance.build_job_url(job_name), {'foo': 'bar'}))


if __name__ == '__main__':
    args = parse_options()

    missing = release_jobs.compute_missing(
        args.distros,
        args.arches,
        args.fqdn,
        rosdistro=args.rosdistro,
        sourcerpm_only=args.sourcerpm_only,
        wet_only=args.wet_only)

    print('')
    print('Missing packages:')
    pp = pprint.PrettyPrinter()
    pp.pprint(missing)

    if args.commit:
        jenkins_instance = jenkins_support.JenkinsConfig_to_handle(jenkins_support.load_server_config_file(jenkins_support.get_default_catkin_rpms_config()))

        missing_by_arch = {}
        for pkg in sorted(missing.iterkeys()):
            dist_archs = missing[pkg]
            for da in dist_archs:
                if da not in missing_by_arch:
                    missing_by_arch[da] = set([])
                missing_by_arch[da].add(pkg)

        print('')
        print('Missing packages by arch:')
        pp.pprint(missing_by_arch)

        triggered = 0
        skipped = 0
        for da in missing_by_arch:
            for pkg in sorted(missing_by_arch[da]):
                try:
                    success = trigger_if_necessary(da, pkg, args.rosdistro, jenkins_instance, missing_by_arch)
                    if success:
                        triggered += 1
                    else:
                        skipped += 1
                except Exception as ex:
                    print("Failed to trigger package '%s' on arch '%s': %s" % (pkg, '_'.join(da), ex))

        print('Triggered %d jobs, skipped %d jobs.' % (triggered, skipped))

    else:
        print('This was not pushed to the server.  If you want to do so use "--commit" to do it for real.')
