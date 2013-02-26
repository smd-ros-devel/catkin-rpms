#!/usr/bin/env python

import os
import sys
import getopt

repos = {
'building': 'http://csc.mcs.sdsmt.edu/smd-ros-building'
}

def check_mock_config(distro, arch='i386', use_ramdisk=False, quiet=False):
    # General Stuff
    user_mock_dir = os.path.join(os.path.expanduser('~'), '.mock_config')
    mock_dir = os.path.normpath('/etc/mock')
    if not os.path.isdir(user_mock_dir):
        os.mkdir(user_mock_dir)
    if not os.path.lexists(os.path.join(user_mock_dir, 'site-defaults.cfg')):
        os.symlink(os.path.join(mock_dir, 'site-defaults.cfg'), os.path.join(user_mock_dir, 'site-defaults.cfg'))
    if not os.path.lexists(os.path.join(user_mock_dir, 'logging.ini')):
        os.symlink(os.path.join(mock_dir, 'logging.ini'), os.path.join(user_mock_dir, 'logging.ini'))

    # Arch-specific config
    with open(os.path.join(mock_dir, 'fedora-%s-%s-rpmfusion_nonfree.cfg' % (distro, arch)), 'r') as f:
        arch_config = f.read()

    arch_config += """
config_opts['root'] += '-ros'
"""
    for name, repo in repos.items():
        arch_config += """
config_opts['yum.conf'] += \"\"\"
[%(name)s]
name=%(name)s
baseurl=%(repo)s/fedora/linux/%(distro)s/%(arch)s/

[%(name)s-debug]
name=%(name)s-debug
baseurl=%(repo)s/fedora/linux/%(distro)s/%(arch)s/debug/

[%(name)s-source]
name=%(name)s-source
baseurl=%(repo)s/fedora/linux/%(distro)s/SRPMS/
\"\"\"
"""%locals()

    if use_ramdisk:
        arch_config += """
config_opts['plugin_conf']['tmpfs_enable'] = True
config_opts['plugin_conf']['tmpfs_opts']['required_ram_mb'] = 3072
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
