.PHONY: all setup clean_dist distro clean install upload push

NAME=rospkg
VERSION=`./setup.py --version`

OUTPUT_DIR=rpm_dist


all:
	echo "noop for rpmbuild"

setup:
	echo "building version ${VERSION}"

clean_dist:
	-rm -f MANIFEST
	-rm -rf dist
	-rm -rf rpm_dist

distro: setup clean_dist
	python setup.py sdist

push: distro
	python setup.py sdist register upload
	scp dist/${NAME}-${VERSION}.tar.gz ipr:/var/www/pr.willowgarage.com/html/downloads/${NAME}

clean: clean_dist
	echo "clean"

install: distro
	sudo checkinstall python setup.py install

rpm_dist:
	# need to convert unstable to each distro and repeat
	python setup.py --command-packages=stdeb.command bdist_rpm

upload-packages: rpm_dist
	dput -u -c dput.cf all-shadow ${OUTPUT_DIR}/${NAME}_${VERSION}-1_amd64.changes 
	dput -u -c dput.cf all-shadow-fixed ${OUTPUT_DIR}/${NAME}_${VERSION}-1_amd64.changes 
	#dput -u -c dput.cf all-ros ${OUTPUT_DIR}/${NAME}_${VERSION}-1_amd64.changes 

upload-building: rpm_dist
	dput -u -c dput.cf all-building ${OUTPUT_DIR}/${NAME}_${VERSION}-1_amd64.changes 

upload: upload-building upload-packages

testsetup:
	echo "running ${NAME} tests"

test: testsetup
	cd test && nosetests
