#!/bin/bash -x

#stop on error
set -o errexit

ROS_REPO_FQDN=@(FQDN)
PACKAGE=@(PACKAGE)
distro=@(DISTRO)
arch=@(ARCH)
base=/var/cache/pbuilder-$distro-$arch


yumconffile=$WORKSPACE/yum.conf

#increment this value if you have changed something that will invalidate base tarballs. #TODO this will need cleanup eventually.
basetgz_version=5

rootdir=$base/yum-conf-$basetgz_version

basetgz=$base/base-$basetgz_version.tgz
output_dir=$WORKSPACE/output
work_dir=$WORKSPACE/work



if [ $arch == arm ] || [ $arch == armhfp ]
then
    mirror=http://ports.ubuntu.com/ubuntu-ports
    debootstrap_type='qemu-debootstrap'
else
    mirror=http://aptproxy.willowgarage.com/us.archive.ubuntu.com/ubuntu
    debootstrap_type='debootstrap'
fi


if [ -e $WORKSPACE/catkin-rpms ]
then
  rm -rf $WORKSPACE/catkin-rpms
fi

git clone git://github.com/smd-ros-devel/catkin-rpms.git $WORKSPACE/catkin-rpms -b master --depth 1


cd $WORKSPACE/catkin-rpms
. setup.sh

#setup the cross platform apt environment
# using sudo since this is shared with pbuilder and if pbuilder is interupted it will leave a sudo only lock file.  Otherwise sudo is not necessary. 
# And you can't chown it even with sudo and recursive 
sudo PYTHONPATH=$PYTHONPATH $WORKSPACE/catkin-rpms/scripts/setup_apt_root.py $distro $arch $rootdir --local-conf-dir $WORKSPACE --mirror $mirror --repo "ros@@http://$ROS_REPO_FQDN/smd-ros-building"

# update yum update
sudo yum update -c $yumconffile -o Apt::Architecture=$arch @(ARCH == 'arm' ? "-o Apt::Architectures::=arm") @(ARCH == 'armhfp' ? "-o Apt::Architectures::=armhfp")

# check precondition that all dependents exist, don't check if no dependencies
@[if DEPENDENTS]
sudo $WORKSPACE/catkin-rpms/scripts/assert_package_dependencies_present.py $rootdir $yumconffile  $PACKAGE
@[end if]

sudo rm -rf $output_dir
mkdir -p $output_dir

sudo rm -rf $work_dir
mkdir -p $work_dir
cd $work_dir


# Pull the sourcerpm
sudo yum source $PACKAGE -c $yumconffile

# extract version number from the dsc file
version=`ls *.dsc | sed s/${PACKAGE}_// | sed s/$distro\.dsc//`
echo "package name ${PACKAGE} version ${version}"


# Setup the pbuilder environment if not existing, or update
if [ ! -e $basetgz ] || [ ! -s $basetgz ] 
then
  #make sure the base dir exists
  sudo mkdir -p $base
  #create the base image
  sudo pbuilder create \
    --distribution $distro \
    --aptconfdir $rootdir/etc/apt \
    --basetgz $basetgz \
    --architecture $arch \
    --mirror $mirror \
    --keyring /etc/apt/trusted.gpg \
    --debootstrap $debootstrap_type \
    --debootstrapopts --arch=$arch \
    --debootstrapopts --keyring=/etc/apt/trusted.gpg
else
  sudo mock --update --basetgz $basetgz
fi


# hooks for changing the binary RPMs to be timestamped
mkdir -p hooks

echo "#!/bin/bash -ex
echo \`env\`
cd /tmp/buildd/*/
apt-get install devscripts -y
prevversion=\`dpkg-parsechangelog | grep Version | awk '{print \$2}'\`
debchange -D $distro -v \$prevversion-\`date +%Y%m%d-%H%M-%z\` 'Time stamping.'
cat debian/changelog
" >> hooks/A50stamp
chmod +x hooks/A50stamp

#  --binary-arch even if "any" type RPMs produce arch specific RPMs
sudo pbuilder  --build \
    --basetgz $basetgz \
    --buildresult $output_dir \
    --debbuildopts \"-b\" \
    --hookdir hooks \
    *.dsc



# Upload invalidate and add to the repo
UPLOAD_DIR=/tmp/upload/${PACKAGE}_${distro}_$arch

ssh rosbuild@@$ROS_REPO_FQDN -- mkdir -p $UPLOAD_DIR
ssh rosbuild@@$ROS_REPO_FQDN -- rm -rf $UPLOAD_DIR/*
scp -r $output_dir/*$distro* rosbuild@@$ROS_REPO_FQDN:$UPLOAD_DIR
ssh rosbuild@@$ROS_REPO_FQDN -- PYTHONPATH=/home/rosbuild/reprepro_updater/src python /home/rosbuild/reprepro_updater/scripts/include_folder.py -d $distro -a $arch -f $UPLOAD_DIR -p $PACKAGE -c --delete --invalidate

# update apt again
sudo yum update -c $yumconffile -o Apt::Architecture=$arch @(ARCH == 'arm' ? "-o Apt::Architectures::=arm") @(ARCH == 'armhfp' ? "-o Apt::Architectures::=armhfp")

# check that the uploaded successfully
sudo $WORKSPACE/catkin-rpms/scripts/assert_package_present.py $rootdir $aptconffile  $PACKAGE
