#!/usr/bin/env python

from __future__ import print_function

import os

def check_mock_config(distro, arch='i386', use_ramdisk=False):
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
config_opts['yum.conf'] += \"\"\"
[ros-shadow]
name=ros-shadow
baseurl=http://csc.mcs.sdsmt.edu/smd-ros-shadow/fedora/linux/%(distro)s/%(arch)s/

[ros-shadow-debug]
name=ros-shadow-debug
baseurl=http://csc.mcs.sdsmt.edu/smd-ros-shadow/fedora/linux/%(distro)s/%(arch)s/debug/
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
        print('Updating ' + 'fedora-%s-%s-ros.cfg'%(distro, arch))
        with open(os.path.join(user_mock_dir, 'fedora-%s-%s-ros.cfg'%(distro, arch)), 'w') as f:
            f.write(arch_config)

    # Done
    print('Mock configuration is OK in %s'%user_mock_dir)
