#!/bin/bash -x

# exit if anything fails
set -o errexit

ROS_REPO_FQDN=@(FQDN)
OS_PLATFORM=@(DISTRO)
ARCH=@(ARCH)
STACK_NAME=@(STACK_NAME)
PACKAGE_NAME=@(PACKAGE)
DISTRO_NAME=@(ROSDISTRO)
PACKAGES_FOR_SYNC=@(PACKAGES_FOR_SYNC)



echo $DISTRO_NAME
echo $STACK_NAME
echo $OS_PLATFORM
echo $ARCH



# Get latest catkin-rpms
if [ -e $WORKSPACE/catkin-rpms ]
then
  rm -rf $WORKSPACE/catkin-rpms
fi

git clone git://github.com/smd-ros-devel/catkin-rpms.git $WORKSPACE/catkin-rpms -b master --depth 1

cd $WORKSPACE/catkin-rpms
. setup.sh


# Building package
@[if IS_METAPACKAGES]
# do not exit if this fails
set +o errexit
@[end if]

single_rpm.py $DISTRO_NAME $STACK_NAME $OS_PLATFORM $ARCH --fqdn $ROS_REPO_FQDN

@[if IS_METAPACKAGES]

# exit if anything fails
set -o errexit

$WORKSPACE/catkin-rpms/scripts/count_ros_packages.py $DISTRO_NAME $OS_PLATFORM $ARCH --count $PACKAGES_FOR_SYNC
ssh rosbuild@@pub8 -- PYTHONPATH=/home/rosbuild/reprepro_updater/src python /home/rosbuild/reprepro_updater/scripts/prepare_sync.py /var/packages/ros-shadow-fixed/fedora -r $DISTRO_NAME -d $OS_PLATFORM -a $ARCH -u http://csc.mcs.sdsmt.edu/smd-ros-building/ -c

@[end if]
