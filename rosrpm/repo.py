# Software License Agreement (BSD License)
#
# Copyright (c) 2010, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Revision $Id: repo.py 16975 2012-09-03 05:02:44Z tfoote $

"""
Utilities for reading state from an RPM repo
"""

import urllib2
import re
from xml.dom import minidom
from StringIO import StringIO
from gzip import GzipFile

from core import redhatify_name, fedora_release_version

class BadRepo(Exception): pass

_Packages_cache = {}
def get_Packages(repo_url, os_platform, arch, cache=None):
    """
    Retrieve the package list from the shadow repo. This routine
    utilizes a cache and should not be invoked in long-running
    processes.
    @raise BadRepo: if repo does not exist
    """
    if cache is None:
        cache = _Packages_cache

    # this is very bad.  This script is assuming the layout of the
    # repo has a subdirectory ubuntu.  I can't parameterize it out
    # without potentially breaking a lot. Using an if statement to get
    # it to work.
    os_version = fedora_release_version(os_platform)
    base_url = repo_url + '/fedora/linux/%(os_version)s/%(arch)s'%locals()
    if base_url in cache:
        return cache[base_url]
    else:
        repomd_url = base_url + '/repodata/repomd.xml'

        try:
            repomd = urllib2.urlopen(repomd_url).read()
        except urllib2.HTTPError:
            raise BadRepo("[%s]: %s"%(repo_url, repomd_url))

        try:
            for data_entry in minidom.parseString(repomd).getElementsByTagName('data'):
                if data_entry.getAttribute('type') == 'primary':
                    packages_url = base_url + '/' + data_entry.getElementsByTagName('location')[0].getAttribute('href')
        except:
            raise BadRepo("[%s]: XML Parse Error %s"%(repo_url, repomd_url))

        try:
            cache[base_url] = retval = minidom.parseString(GzipFile(fileobj=StringIO((urllib2.urlopen(packages_url).read()))).read())
        except urllib2.HTTPError:
            raise BadRepo("[%s]: %s"%(repo_url, base_url))
    return retval
    
def parse_Packages(packagelist):
    """
    Parse RPM Packages list into (package, version, depends) tuples
    @return: parsed tuples or None if packagelist is None
    """
    package_deps = []
    package = deps = version = distro = None
    for package in packagelist.getElementsByTagName('package'):
        if package.getAttribute('type') != 'rpm':
            continue
        name = package.getElementsByTagName('name')[0].firstChild
        name_split = name.data.split('-')
        if name_split[0] != 'ros':
            continue
        version = package.getElementsByTagName('version')[0]
        deps = []

        for l1 in package.getElementsByTagName('format'):
            for l2 in l1.getElementsByTagName('rpm:requires'):
                for dep in l2.getElementsByTagName('rpm:entry'):
                    if dep.getAttribute('name')[0] == '/':
                        continue
                    deps.append(dep.getAttribute('name'))
        package_deps.append((name.data, version.getAttribute('ver') + '-' + version.getAttribute('rel'), deps, name_split[1]))
    return package_deps

def load_Packages(repo_url, os_platform, arch, cache=None):
    """
    Download and parse RPM Packages list into (package, version, depends) tuples
    """
    return parse_Packages(get_Packages(repo_url, os_platform, arch, cache))

def rpm_in_repo(repo_url, rpm_name, rpm_version, os_platform, arch, use_regex=True, cache=None):
    """
    @param cache: dictionary to store Packages list for caching
    """
    packagelist = get_Packages(repo_url, os_platform, arch, cache)
    if not use_regex:
        for package in packagelist.getElementsByTagName('package'):
            if package.getElementsByTagName('name')[0].firstChild.data == rpm_name:
                version = package.getElementsByTagName('version')[0]
                if version.getAttribute('ver') + '-' + version.getAttribute('rel') == rpm_version:
                    return True
    else:
        for package in packagelist.getElementsByTagName('package'):
            if re.search(rpm_name, package.getElementsByTagName('name')[0].firstChild.data) is not None:
                version = package.getElementsByTagName('version')[0]
                if re.search(rpm_version, version.getAttribute('ver') + '-' + version.getAttribute('rel')) is not None:
                    return True
    return None

def get_depends(repo_url, rpm_name, os_platform, arch):
    """
    Get all RPM package dependencies by scraping the Packages
    list. We mainly use this for invalidation logic. 
    """
    # There is probably something much simpler we could do, but this
    # more robust to any bad state we may have caused to the shadow
    # repo.
    package_deps = load_Packages(repo_url, os_platform, arch)
    done = False
    queue = [rpm_name]
    depends = set()
    # This is not particularly efficient, but it does not need to
    # be. Basically, we find all the packages that depend on the
    # package, then find all the packages that depends on those,
    # etc...
    while queue:
        next  = queue[0]
        queue = queue[1:]
        for package, _, deps, _ in package_deps:
            #strip of version specifications from deps
            deps = [d.split()[0] for d in deps]
            if package not in depends and next in deps:
                queue.append(package)
                depends.add(package)
    return list(depends)

def get_stack_version(packageslist, distro_name, stack_name):
    """
    Get the ROS version number of the stack in the repository
    """
    rpm_name = "ros-%s-%s"%(distro_name, redhatify_name(stack_name))
    match = [vm for sm, vm, _, _ in packageslist if sm == rpm_name]
    if match:
        return match[0].split('-')[0]
    else:
        return None

def get_repo_version(repo_url, distro, os_platform, arch):
    """
    Return the greatest build-stamp for any RPM in the repository
    """
    packagelist = load_Packages(repo_url, os_platform, arch)
    return max(['0'] + [x[1][x[1].find('-')+1:x[1].find('.fc')] for x in packagelist if x[3] == distro.release_name])

