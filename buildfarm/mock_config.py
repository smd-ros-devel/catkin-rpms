#!/usr/bin/env python

import os
import sys
import getopt

repos = {
'building': 'http://csc.mcs.sdsmt.edu/smd-ros-building',
# Underlay should only be here until the packages are in the official Fedora repo
'underlay': 'http://csc.mcs.sdsmt.edu/smd-ros-underlay'

}

def check_mock_config(distro, arch='i386', use_ramdisk=True, quiet=False):
    # General Stuff
    user_mock_dir = os.path.join(os.path.expanduser('~'), '.mock_config')
    mock_dir = os.path.normpath('/etc/mock')
    if not os.path.isdir(user_mock_dir):
        os.mkdir(user_mock_dir)
    if not os.path.lexists(os.path.join(user_mock_dir, 'site-defaults.cfg')):
        os.symlink(os.path.join(mock_dir, 'site-defaults.cfg'), os.path.join(user_mock_dir, 'site-defaults.cfg'))
    if not os.path.lexists(os.path.join(user_mock_dir, 'logging.ini')):
        os.symlink(os.path.join(mock_dir, 'logging.ini'), os.path.join(user_mock_dir, 'logging.ini'))

    if arch == 'srpm':
        use_arch = 'i386'
    else:
        use_arch = arch

    # Arch-specific config
    with open(os.path.join(mock_dir, 'fedora-%s-%s-rpmfusion_nonfree.cfg' % (distro, use_arch)), 'r') as f:
        arch_config = f.read()

    arch_config += """
config_opts['root'] += '-ros'
"""
    for name, repo in repos.items():
        arch_config += """
config_opts['yum.conf'] += \"\"\"
[%(name)s]
name=%(name)s
baseurl=%(repo)s/fedora/linux/%(distro)s/%(use_arch)s/
metadata_expire=1
keepcache=0
http_caching=none

[%(name)s-debug]
name=%(name)s-debug
baseurl=%(repo)s/fedora/linux/%(distro)s/%(use_arch)s/debug/
metadata_expire=1
keepcache=0
http_caching=none
enabled=0

[%(name)s-source]
name=%(name)s-source
baseurl=%(repo)s/fedora/linux/%(distro)s/SRPMS/
metadata_expire=1
keepcache=0
http_caching=none
enabled=0
\"\"\"
"""%locals()

    arch_config += """
config_opts['yum.conf'] += \"\"\"
[fedora-19]
name=fedora-19
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-19&arch=x86_64
failovermethod=priority
includepkgs=eigen3-devel
\"\"\"
"""

    if use_ramdisk:
        arch_config += """
config_opts['plugin_conf']['tmpfs_enable'] = True
config_opts['plugin_conf']['tmpfs_opts']['required_ram_mb'] = 4096
config_opts['plugin_conf']['tmpfs_opts']['max_fs_size'] = '20G'
"""

    user_arch_config = ""
    if os.path.exists(os.path.join(user_mock_dir, 'fedora-%s-%s-ros.cfg'%(distro, arch))):
        with open(os.path.join(user_mock_dir, 'fedora-%s-%s-ros.cfg'%(distro, arch)), 'r') as f:
            user_arch_config = f.read()

    if user_arch_config != arch_config:
        if not quiet:
            print('Updating ' + 'fedora-%s-%s-ros.cfg'%(distro, arch))
        with open(os.path.join(user_mock_dir, 'fedora-%s-%s-ros.cfg'%(distro, arch)), 'w') as f:
            f.write(arch_config)

    # Done
    if not quiet:
        print('Mock configuration is OK in %s'%user_mock_dir)

    return user_mock_dir

if __name__ == "__main__":
    distro = None
    arch = 'i386'
    try:
        opts, args = getopt.getopt(sys.argv[1:],'d:a:',['ifile=','ofile='])
    except getopt.GetoptError:
        print('Usage: mock_config.py -d <fedora_version> -a <arch>')
        sys.exit(1)

    for opt, arg in opts:
        if opt in ('-d', '--distro'):
            distro = arg
        elif opt in ('-a', '--arch'):
            arch = arg

    if not distro:
        print >> sys.stderr, 'ERROR: No valid distro specified'
        print('Usage: mock_config.py -d <fedora_version> -a <arch>')
        sys.exit(1)

    print(check_mock_config(distro, arch, quiet=True))
