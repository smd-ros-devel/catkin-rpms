#!/usr/bin/env python

from __future__ import print_function
import argparse
import os
import sys
import tempfile

from buildfarm import jenkins_support, release_jobs

import rospkg.distro

from buildfarm.rosdistro import Rosdistro, redhatify_package_name

URL_PROTOTYPE = 'https://raw.github.com/smd-ros-devel/rosdistro/master/releases/%s.yaml'


def parse_options():
    parser = argparse.ArgumentParser(
             description='Create a set of jenkins jobs '
             'for source RPMs and binary RPMs for a catkin package.')
    parser.add_argument('--fqdn', dest='fqdn',
           help='The source repo to push to, fully qualified domain name',
           default='csc.mcs.sdsmt.edu')
    parser.add_argument(dest='rosdistro',
           help='The ros distro. fuerte, groovy, hydro, ...')
    parser.add_argument('--distros', nargs='+',
           help='A list of Red Hat distros. Default: %(default)s',
           default=[])
    parser.add_argument('--arches', nargs='+',
           help='A list of Red Hat architectures. Default: %(default)s',
           default=['i386', 'x86_64'])
    parser.add_argument('--commit', dest='commit',
           help='Really?', action='store_true', default=False)
    parser.add_argument('--delete', dest='delete',
           help='Delete extra jobs', action='store_true', default=False)
    parser.add_argument('--no-update', dest='skip_update',
           help='Assume packages have already been downloaded', action='store_true', default=False)
    parser.add_argument('--wet-only', dest='wet_only',
           help='Only setup wet jobs', action='store_true', default=False)
    parser.add_argument('--repo-workspace', action='store',
           help='A directory into which all the repositories will be checked out into.')
    parser.add_argument('--repos', nargs='+',
           help='A list of repository (or stack) names to create. Default: creates all')
    args = parser.parse_args()
    if args.repos and args.delete:
        parser.error('A set of repos to create can not be combined with the --delete option.')
    return args


def doit(rd, distros, arches, fqdn, jobs_graph, rosdistro, packages, dry_maintainers, commit=False, delete_extra_jobs=False, whitelist_repos=None):
    jenkins_instance = None
    if args.commit or delete_extra_jobs:
        jenkins_instance = jenkins_support.JenkinsConfig_to_handle(jenkins_support.load_server_config_file(jenkins_support.get_default_catkin_debs_config()))

    # Figure out default distros.  Command-line arg takes precedence; if
    # it's not specified, then read targets.yaml.
    if distros:
        default_distros = distros
    else:
        default_distros = rd.get_target_distros()

    # TODO: pull raches from rosdistro
    target_arches = arches

    # We take the intersection of repo-specific targets with default
    # targets.
    results = {}

    for repo_name in sorted(rd.get_repo_list()):
        if whitelist_repos and repo_name not in whitelist_repos:
            continue

        r = rd.get_repo(repo_name)
        #todo add support for specific targets, needed in rosdistro.py too
        #if 'target' not in r or r['target'] == 'all':
        target_distros = default_distros
        #else:
        #    target_distros = list(set(r['target']) & set(default_distros))

        print ('Configuring WET repo "%s" at "%s" for "%s"' % (r.name, r.url, target_distros))

        for p in sorted(r.packages.iterkeys()):
            if not r.version:
                print('- skipping "%s" since version is null' % p)
                continue
            pkg_name = rd.redhatify_package_name(p)
            results[pkg_name] = release_jobs.doit(r.url,
                 pkg_name,
                 packages[p],
                 target_distros,
                 target_arches,
                 fqdn,
                 jobs_graph,
                 rosdistro=rosdistro,
                 short_package_name=p,
                 commit=commit,
                 jenkins_instance=jenkins_instance)
            #time.sleep(1)
            #print ('individual results', results[pkg_name])

    if args.wet_only:
        print ("wet only selected, skipping dry and delete")
        return results

    if rosdistro == 'backports':
        print ("No dry backports support")
        return results

    if rosdistro == 'fuerte':
        packages_for_sync = 300
    else:
        packages_for_sync = 485

    #dry stacks
    # dry dependencies
    d = rospkg.distro.load_distro(rospkg.distro.distro_uri(rosdistro))

    for s in sorted(d.stacks.iterkeys()):
        if whitelist_repos and s not in whitelist_repos:
            continue
        print ("Configuring DRY job [%s]" % s)
        if not d.stacks[s].version:
            print('- skipping "%s" since version is null' % s)
            continue
        results[rd.redhatify_package_name(s)] = release_jobs.dry_doit(s, dry_maintainers[s], default_distros, target_arches, fqdn, rosdistro, jobgraph=jobs_graph, commit=commit, jenkins_instance=jenkins_instance, packages_for_sync=packages_for_sync)
        #time.sleep(1)

    # special metapackages job
    if not whitelist_repos or 'metapackages' in whitelist_repos:
        results[rd.redhatify_package_name('metapackages')] = release_jobs.dry_doit('metapackages', [], default_distros, target_arches, fqdn, rosdistro, jobgraph=jobs_graph, commit=commit, jenkins_instance=jenkins_instance, packages_for_sync=packages_for_sync)

    if delete_extra_jobs:
        assert(not whitelist_repos)
        # clean up extra jobs
        configured_jobs = set()

        for jobs in results.values():
            release_jobs.summarize_results(*jobs)
            for e in jobs:
                configured_jobs.update(set(e))

        existing_jobs = set([j['name'] for j in jenkins_instance.get_jobs()])
        relevant_jobs = existing_jobs - configured_jobs
        relevant_jobs = [j for j in relevant_jobs if rosdistro in j and ('_sourcerpm' in j or '_binaryrpm' in j)]

        for j in relevant_jobs:
            print('Job "%s" detected as extra' % j)
            if commit:
                jenkins_instance.delete_job(j)
                print('Deleted job "%s"' % j)

    return results


if __name__ == '__main__':
    args = parse_options()

    repo = 'http://%s/repos/building' % args.fqdn

    print('Loading rosdistro %s' % args.rosdistro)

    rd = Rosdistro(args.rosdistro)

    workspace = args.repo_workspace
    if not workspace:
        workspace = os.path.join(tempfile.gettempdir(), 'repo-workspace-%s' % args.rosdistro)

    if args.rosdistro != 'fuerte':
        from buildfarm import dependency_walker
        packages = dependency_walker.get_packages(workspace, rd, skip_update=args.skip_update)
        dependencies = dependency_walker.get_jenkins_dependencies(args.rosdistro, packages)
    else:
        from buildfarm import dependency_walker_fuerte
        stacks = dependency_walker_fuerte.get_stacks(workspace, rd._repoinfo, args.rosdistro, skip_update=args.skip_update)
        dependencies = dependency_walker_fuerte.get_dependencies(args.rosdistro, stacks)
        packages = stacks

    # even for wet_only the dry packages need to be consider, else they are not added as downstream dependencies for the wet jobs
    stack_depends, dry_maintainers = release_jobs.dry_get_stack_dependencies(args.rosdistro)
    dry_jobgraph = release_jobs.dry_generate_jobgraph(args.rosdistro, dependencies, stack_depends)

    combined_jobgraph = {}
    for k, v in dependencies.iteritems():
        combined_jobgraph[k] = v
    for k, v in dry_jobgraph.iteritems():
        combined_jobgraph[k] = v

    # setup a job triggered by all other rpmjobs
    combined_jobgraph[redhatify_package_name(args.rosdistro, 'metapackages')] = combined_jobgraph.keys()

    results_map = doit(
        rd,
        args.distros,
        args.arches,
        args.fqdn,
        combined_jobgraph,
        rosdistro=args.rosdistro,
        packages=packages,
        dry_maintainers=dry_maintainers,
        commit=args.commit,
        delete_extra_jobs=args.delete,
        whitelist_repos=args.repos)

    if not args.commit:
        print('This was not pushed to the server.  If you want to do so use "--commit" to do it for real.')
