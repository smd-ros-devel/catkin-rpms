#!/bin/bash

#stop on error
set -o errexit

RELEASE_URI=@(RELEASE_URI)
FQDN=@(FQDN)
PACKAGE=@(PACKAGE)
ROSDISTRO=@(ROSDISTRO)
DISTRO=@(DISTRO)
SHORT_PACKAGE_NAME=@(SHORT_PACKAGE_NAME)

if [ -e $WORKSPACE/catkin-rpms ]
then
  rm -rf $WORKSPACE/catkin-rpms
fi

echo "Fetching catkin-rpms"
git clone git://github.com/smd-ros-devel/catkin-rpms.git $WORKSPACE/catkin-rpms -b master --depth 1

cd $WORKSPACE/catkin-rpms 
. setup.sh

echo "Cleaning up"
rm -rf $WORKSPACE/output
rm -rf $WORKSPACE/workspace

echo "Generating SRPM"
$WORKSPACE/catkin-rpms/scripts/generate_sourcerpm $RELEASE_URI $PACKAGE $ROSDISTRO $SHORT_PACKAGE_NAME --working $WORKSPACE/workspace --output $WORKSPACE/output --repo-fqdn $FQDN --distro $DISTRO
