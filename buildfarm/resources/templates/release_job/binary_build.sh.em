#!/bin/bash -x

#stop on error
set -o errexit


FQDN=@(FQDN)
PACKAGE=@(PACKAGE)
DISTRO=@(DISTRO)
DISTRO_VER=@(DISTRO_VER)
ARCH=@(ARCH)

sudo yum install -q -y mock mock-rpmfusion-nonfree

if [ -e $WORKSPACE/catkin-rpms ]
then
  rm -rf $WORKSPACE/catkin-rpms
fi

git clone git://github.com/smd-ros-devel/catkin-rpms.git $WORKSPACE/catkin-rpms -b master --depth 1

cd $WORKSPACE/catkin-rpms
. setup.sh

rm -rf $WORKSPACE/output
rm -rf $WORKSPACE/workspace

mkdir -p $WORKSPACE/output
mkdir -p $WORKSPACE/workspace

cd $WORKSPACE/workspace

# Check and update mock root
MOCK_USER_DIR=`$WORKSPACE/catkin-rpms/buildfarm/mock_config.py -d $DISTRO_VER -a $ARCH`
/usr/bin/mock --quiet --configdir $MOCK_USER_DIR --root fedora-$DISTRO_VER-$ARCH-ros --init
MOCK_ROOT=`/usr/bin/mock --quiet --configdir $MOCK_USER_DIR --root fedora-$DISTRO_VER-$ARCH-ros --print-root-path`

# Pull the sourcerpm
yumdownloader --source --installroot $MOCK_ROOT $PACKAGE

# Extract version number from the source RPM
VERSION=`rpm --queryformat="%{VERSION}" -qp *.src.rpm`
echo "package name ${PACKAGE} version ${VERSION}"

# Actually perform the mockbuild
/usr/bin/mock --quiet --configdir $MOCK_USER_DIR --root fedora-$DISTRO_VER-$ARCH-ros --resultdir $WORKSPACE/output  --rebuild *.src.rpm

# Remove the source RPM (that's already in the repo)
rm -f $WORKSPACE/output/*.src.rpm

# Upload invalidate and add to the repo
UPLOAD_DIR=/tmp/upload/${PACKAGE}_${DISTRO}_$ARCH

ssh rosbuild@@$FQDN -- mkdir -p $UPLOAD_DIR
ssh rosbuild@@$FQDN -- rm -rf $UPLOAD_DIR/*
scp -r $WORKSPACE/output/*.rpm rosbuild@@$ROS_REPO_FQDN:$UPLOAD_DIR
ssh rosbuild@@$ROS_REPO_FQDN -- PYTHONPATH=/home/rosbuild/reprepro_updater/src python /home/rosbuild/repoman/scripts/include_folder.py -d $distro -a $arch -f $UPLOAD_DIR -p $PACKAGE -c --delete --invalidate

# Check that the uploaded successfully
#sudo $WORKSPACE/catkin-rpms/scripts/assert_package_present.py $rootdir $aptconffile  $PACKAGE
