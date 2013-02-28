#!/usr/bin/env python

from __future__ import print_function
import em
import pkg_resources
import os
import re
import sys
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import urllib
import urllib2
import yaml
import datetime
from rospkg.distro import load_distro, distro_uri

from rosdistro import redhatify_package_name, Rosdistro

from rosrpm.core import fedora_release_version
from rosrpm import repo

from . import jenkins_support

import jenkins


class Templates(object):
    template_dir = os.path.dirname(__file__)
    config_sourcerpm = pkg_resources.resource_string('buildfarm', 'resources/templates/release_job/config.source.xml.em')  # A config.xml template for sourcerpms.
    command_sourcerpm = pkg_resources.resource_string('buildfarm', 'resources/templates/release_job/source_build.sh.em')  # The bash script that the sourcerpms config.xml runs.
    command_binaryrpm = pkg_resources.resource_string('buildfarm', 'resources/templates/release_job/binary_build.sh.em')  # builds binary RPMs.
    config_binaryrpm = pkg_resources.resource_string('buildfarm', 'resources/templates/release_job/config.binary.xml.em')  # A config.xml template for something that runs a shell script
    config_dry_binaryrpm = pkg_resources.resource_string('buildfarm', 'resources/templates/dry_release/config.xml.em')  # A config.xml template for something that runs a shell script
    command_dry_binaryrpm = pkg_resources.resource_string('buildfarm', 'resources/templates/dry_release/build.sh.em')  # A config.xml template for something that runs a shell script


def expand(config_template, d):
    s = em.expand(config_template, **d)
    return s


def compute_missing(distros, arches, fqdn, rosdistro, sourcerpm_only=False, wet_only=False):
    """ Compute what packages are missing from a repo based on the rosdistro files, both wet and dry. """

    repo_url = 'http://%s/smd-ros-building' % fqdn

    rd = Rosdistro(rosdistro)
    # We take the intersection of repo-specific targets with default
    # targets.

    if distros:
        target_distros = distros
    else:
        target_distros = rd.get_target_distros()

    missing = {}
    for short_package_name in rd.get_package_list():
        #print ('Analyzing WET stack "%s" for "%s"' % (r['url'], target_distros))

        # todo check if sourcerpm is present with the right version
        rpm_name = redhatify_package_name(rosdistro, short_package_name)
        expected_version = rd.get_version(short_package_name, full_version=True)

        missing[short_package_name] = []
        for d in target_distros:
            d_ver = fedora_release_version(d)
            if not repo.rpm_in_repo(repo_url, rpm_name, str(expected_version) + "\.fc" + d_ver, d, 'SRPMS'):
                missing[short_package_name].append((d, 'SRPMS'))
            if not sourcerpm_only:
                for a in arches:
                    if not repo.rpm_in_repo(repo_url, rpm_name, str(expected_version) + "\.fc" + d_ver, d, a):
                        missing[short_package_name].append((d, a))

    if not sourcerpm_only and not wet_only:
        #dry stacks
        # dry dependencies
        dist = load_distro(distro_uri(rosdistro))

        distro_arches = []
        for d in target_distros:
            for a in arches:
                distro_arches.append((d, a))

        for s in dist.stacks:
            #print ("Analyzing DRY job [%s]" % s)
            expected_version = dry_get_stack_version(s, dist)

            # sanitize undeclared versions for string substitution
            if not expected_version:
                expected_version = ''
            missing[s] = []
            # for each distro arch check if the RPM is present. If not trigger the build.
            for (d, a) in distro_arches:
                if not repo.rpm_in_repo(repo_url, redhatify_package_name(rosdistro, s), expected_version + "\.fc" + fedora_release_version(d), d, a):
                    missing[s].append((d, a))

    return missing


# dry dependencies
def dry_get_stack_info(stackname, version):
    y = urllib.urlopen('https://csc.mcs.sdsmt.edu/svn/release/download/stacks/%(stackname)s/%(stackname)s-%(version)s/%(stackname)s-%(version)s.yaml' % locals())
    return yaml.load(y.read())


def dry_get_stack_version(stackname, rosdistro_obj):
    if not stackname in rosdistro_obj.stacks:
        raise Exception("Stack %s not in distro %s" % (stackname, rosdistro_obj.release_name))
    st = rosdistro_obj.stacks[stackname]
    return st.version


def dry_get_versioned_dependency_tree(rosdistro):
    url = distro_uri(rosdistro)
    try:
        d = load_distro(url)
    except urllib2.URLError as ex:
        print ("Loading distro from '%s'failed with URLError %s" % (url, ex), file=sys.stderr)
        raise
    dependency_tree = {}
    versions = {}
    maintainer_dict = {}
    for s in d.stacks:
        version = d.stacks[s].version
        versions[s] = version
        yaml_info = dry_get_stack_info(s, version)
        if 'depends' in yaml_info:
            dependency_tree[s] = yaml_info['depends']
        else:
            dependency_tree[s] = []
        maintainers = []
        if 'maintainer' in yaml_info:
            maintainers = _extract_emails(yaml_info['maintainer'])
        if not maintainers and 'contact' in yaml_info:
            maintainers = _extract_emails(yaml_info['contact'])
        maintainer_dict[s] = maintainers
    return dependency_tree, versions, maintainer_dict


def _extract_emails(value):
    values = re.split(' |,|;|<|>|\(|\)|\[|\]|\n|\r', value)
    return [v for v in values if v.find('@', 1, -3) != -1]


def dry_get_stack_dependencies(rosdistro):
    if rosdistro == 'backports':
        return {}, {}

    (stack_depends, _, maintainers) = dry_get_versioned_dependency_tree(rosdistro)
    return stack_depends, maintainers


def dry_generate_jobgraph(rosdistro, wet_jobgraph, stack_depends):
    jobgraph = {}
    for key, val in stack_depends.iteritems():
        dry_depends = [redhatify_package_name(rosdistro, p) for p in val]

        untracked_wet_packages = [p for p in dry_depends if p in wet_jobgraph]

        extra_packages = set()
        for p in untracked_wet_packages:
            #print("adding packages for %s - [%s] " % (p, ', '.join(wet_jobgraph[p])) )
            extra_packages.update(wet_jobgraph[p])

        jobgraph[redhatify_package_name(rosdistro, key)] = dry_depends + list(extra_packages)
    return jobgraph


def compare_configs(a, b):
    """Return True if the configs are the same, except the
    description, else False"""
    aroot = ET.fromstring(a)
    broot = ET.fromstring(b)
    aroot.find('description').text = ''
    broot.find('description').text = ''
    return ET.tostring(aroot) == ET.tostring(broot)


def create_jenkins_job(jobname, config, jenkins_instance):
    try:
        jobs = jenkins_instance.get_jobs()
        print("working on job", jobname)
        if jobname in [job['name'] for job in jobs]:
            remote_config = jenkins_instance.get_job_config(jobname)
            if not compare_configs(remote_config, config):
                jenkins_instance.reconfig_job(jobname, config)
            else:
                print("Skipping %s as config is the same" % jobname)

        else:
            jenkins_instance.create_job(jobname, config)
        return True
    except jenkins.JenkinsException as ex:
        print('Failed to configure "%s" with error: %s' % (jobname, ex), file=sys.stderr)
        return False


def sourcerpm_job_name(packagename, distro):
    return "%(packagename)s_sourcerpm_%(distro)s" % locals()


def create_sourcerpm_config(d):
    d['COMMAND'] = escape(expand(Templates.command_sourcerpm, d))
    d['TIMESTAMP'] = datetime.datetime.now()
    return expand(Templates.config_sourcerpm, d)


def create_binaryrpm_config(d):
    d['TIMESTAMP'] = datetime.datetime.now()
    d['COMMAND'] = escape(expand(Templates.command_binaryrpm, d))
    return expand(Templates.config_binaryrpm, d)


def create_dry_binaryrpm_config(d):
    d['COMMAND'] = escape(expand(Templates.command_dry_binaryrpm, d))
    d['TIMESTAMP'] = datetime.datetime.now()
    return expand(Templates.config_dry_binaryrpm, d)


def binaryrpm_job_name(packagename, distro, arch):
    return "%(packagename)s_binaryrpm_%(distro)s_%(arch)s" % locals()


def calc_child_jobs(packagename, distro, arch, jobgraph):
    children = []
    if jobgraph:
        for package, deps in jobgraph.iteritems():
            if packagename in deps:
                children.append(binaryrpm_job_name(package, distro, arch))
    return children


def add_dependent_to_dict(packagename, jobgraph):
    dependents = {}
    if jobgraph:
        if packagename in jobgraph:
            dependents = jobgraph[packagename]
    return dependents


def dry_binaryrpm_jobs(stackname, dry_maintainers, rosdistro, distros, arches, fqdn, jobgraph, packages_for_sync):
    jenkins_config = jenkins_support.load_server_config_file(jenkins_support.get_default_catkin_rpms_config())
    package = redhatify_package_name(rosdistro, stackname)
    d = dict(
        FQDN=fqdn,
        PACKAGE=package,
        ROSDISTRO=rosdistro,
        STACK_NAME=stackname,
        NOTIFICATION_EMAIL=' '.join(dry_maintainers),
        USERNAME=jenkins_config.username,
        IS_METAPACKAGES=(stackname == 'metapackages'),
        PACKAGES_FOR_SYNC=str(packages_for_sync)
    )
    jobs = []
    for distro in distros:
        for arch in arches:
            d['ARCH'] = arch
            d['DISTRO'] = distro
            d['DISTRO_VER'] = fedora_release_version(distro)

            d["CHILD_PROJECTS"] = calc_child_jobs(package, distro, arch, jobgraph)
            d["DEPENDENTS"] = "True"
            config = create_dry_binaryrpm_config(d)
            #print(config)
            job_name = binaryrpm_job_name(package, distro, arch)
            jobs.append((job_name, config))
            #print ("config of %s is %s" % (job_name, config))
    return jobs


def binaryrpm_jobs(package, maintainer_emails, distros, arches, fqdn, jobgraph):
    jenkins_config = jenkins_support.load_server_config_file(jenkins_support.get_default_catkin_rpms_config())
    d = dict(
        DISTROS=distros,
        FQDN=fqdn,
        PACKAGE=package,
        NOTIFICATION_EMAIL=' '.join(maintainer_emails),
        USERNAME=jenkins_config.username
    )
    jobs = []
    for distro in distros:
        d['DISTRO'] = distro
        d['DISTRO_VER'] = fedora_release_version(distro)
        for arch in arches:
            d['ARCH'] = arch
            d["CHILD_PROJECTS"] = calc_child_jobs(package, distro, arch, jobgraph)
            d["DEPENDENTS"] = add_dependent_to_dict(package, jobgraph)
            config = create_binaryrpm_config(d)
            #print(config)
            job_name = binaryrpm_job_name(package, distro, arch)
            jobs.append((job_name, config))
    return jobs


def sourcerpm_jobs(package, maintainer_emails, distros, fqdn, release_uri, child_projects, rosdistro, short_package_name):
    jenkins_config = jenkins_support.load_server_config_file(jenkins_support.get_default_catkin_rpms_config())

    d = dict(
        RELEASE_URI=release_uri,
        RELEASE_BRANCH='master',
        FQDN=fqdn,
        DISTROS=distros,
        CHILD_PROJECTS=child_projects,
        PACKAGE=package,
        NOTIFICATION_EMAIL=' '.join(maintainer_emails),
        ROSDISTRO=rosdistro,
        SHORT_PACKAGE_NAME=short_package_name,
        USERNAME=jenkins_config.username
    )
    jobs = []
    for distro in distros:
        d['DISTRO'] = distro
        d['DISTRO_VER'] = fedora_release_version(distro)
        jobs.append((sourcerpm_job_name(package, distro), create_sourcerpm_config(d)))
    return jobs


def dry_doit(package, dry_maintainers, distros, arches, fqdn, rosdistro, jobgraph, commit, jenkins_instance, packages_for_sync):

    jobs = dry_binaryrpm_jobs(package, dry_maintainers, rosdistro, distros, arches, fqdn, jobgraph, packages_for_sync)

    successful_jobs = []
    failed_jobs = []
    for job_name, config in jobs:
        if commit:
            try:
                ret_val = create_jenkins_job(job_name, config, jenkins_instance)
                if ret_val:
                    successful_jobs.append(job_name)
                else:
                    failed_jobs.append(job_name)
            except urllib2.URLError as ex:
                print ("Job creation failed with URLError %s" % ex, file=sys.stderr)
                failed_jobs.append(job_name)

    unattempted_jobs = [job for (job, config) in jobs if job not in successful_jobs and job not in failed_jobs]

    return (unattempted_jobs, successful_jobs, failed_jobs)


def doit(release_uri, package_name, package, distros, arches, fqdn, job_graph, rosdistro, short_package_name, commit, jenkins_instance):
    maintainer_emails = ['logans@cottsay.net']
    binary_jobs = binaryrpm_jobs(package_name, maintainer_emails, distros, arches, fqdn, job_graph)
    child_projects = zip(*binary_jobs)[0]  # unzip the binary_jobs tuple
    source_jobs = sourcerpm_jobs(package_name, maintainer_emails, distros, fqdn, release_uri, child_projects, rosdistro, short_package_name)
    jobs = source_jobs + binary_jobs
    successful_jobs = []
    failed_jobs = []
    for job_name, config in jobs:
        if commit:
            if create_jenkins_job(job_name, config, jenkins_instance):
                successful_jobs.append(job_name)
            else:
                failed_jobs.append(job_name)
    unattempted_jobs = [job for (job, config) in jobs if job not in successful_jobs and job not in failed_jobs]

    return (unattempted_jobs, successful_jobs, failed_jobs)


def summarize_results(unattempted_jobs, successful_jobs, failed_jobs):
    print('=' * 80)
    jobs = set(unattempted_jobs).union(set(successful_jobs)).union(set(failed_jobs))
    print ('Summary: %d jobs configured.  Listed below.' % len(jobs))
    print ('Unexecuted: %d' % len(unattempted_jobs))
    for job_name in unattempted_jobs:
        print ("  %s" % job_name)
    print ('Successful: %d' % len(successful_jobs))
    for job_name in successful_jobs:
        print ("  %s" % job_name)
    print ('Failed: %d' % len(failed_jobs))
    for job_name in failed_jobs:
        print ("  %s" % job_name)
    print('=' * 80)
