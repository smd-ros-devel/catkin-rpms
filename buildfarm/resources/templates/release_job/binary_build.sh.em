#!/bin/bash

#stop on error
set -o errexit


FQDN=@(FQDN)
PACKAGE=@(PACKAGE)
DISTRO=@(DISTRO)
DISTRO_VER=@(DISTRO_VER)
ARCH=@(ARCH)

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
mount | grep -q mock_chroot_tmpfs && sudo umount mock_chroot_tmpfs || echo "mock_chroot_tmpfs is not mounted! hooray!"
MOCK_USER_DIR=`$WORKSPACE/catkin-rpms/buildfarm/mock_config.py -d $DISTRO_VER -a $ARCH`
/usr/bin/mock --quiet --configdir $MOCK_USER_DIR --root fedora-$DISTRO_VER-$ARCH-ros --resultdir $WORKSPACE/output --scrub=yum-cache
/usr/bin/mock --quiet --configdir $MOCK_USER_DIR --root fedora-$DISTRO_VER-$ARCH-ros --resultdir $WORKSPACE/output --init
/usr/bin/mock --quiet --configdir $MOCK_USER_DIR --root fedora-$DISTRO_VER-$ARCH-ros --resultdir $WORKSPACE/output --copyout /etc/yum.conf $WORKSPACE/workspace/

# I think this might be a mock bug...but things don't get umounted after the copyout
sudo umount mock_chroot_tmpfs || echo "Umount failed...this is OK"

# Pull the sourcerpm
yum --quiet clean headers packages metadata dbcache plugins expire-cache
yumdownloader --quiet --disablerepo="*" --enablerepo=building --source --config $WORKSPACE/workspace/yum.conf --destdir $WORKSPACE/workspace $PACKAGE

# Extract version number from the source RPM
VERSION=`rpm --queryformat="%{VERSION}" -qp $WORKSPACE/workspace/*.src.rpm`
echo "package name ${PACKAGE} version ${VERSION}"

# Actually perform the mockbuild
/usr/bin/mock --quiet --configdir $MOCK_USER_DIR --root fedora-$DISTRO_VER-$ARCH-ros --resultdir $WORKSPACE/output  --rebuild $WORKSPACE/workspace/*.src.rpm

# Remove the source RPM (that's already in the repo)
rm -f $WORKSPACE/output/*.src.rpm

# Upload invalidate and add to the repo
UPLOAD_DIR=/tmp/upload/${PACKAGE}_${DISTRO}_$ARCH

ssh rosbuild@@$FQDN -- rm -rf $UPLOAD_DIR
ssh rosbuild@@$FQDN -- mkdir -p $UPLOAD_DIR
scp $WORKSPACE/output/*.rpm rosbuild@@$FQDN:$UPLOAD_DIR
ssh rosbuild@@$FQDN -- PYTHONPATH=/home/rosbuild/reprepro_updater/src python /home/rosbuild/repoman/scripts/include_folder.py -d $DISTRO_VER -a $ARCH -f $UPLOAD_DIR -p $PACKAGE -c --delete --invalidate

# Check that the uploaded successfully
#sudo $WORKSPACE/catkin-rpms/scripts/assert_package_present.py $rootdir $aptconffile  $PACKAGE
