server.yaml
===========

To use this it will look for server.yaml in $ROS_HOME/catkin-rpms for credentials.  Put your Jenkins login in this file.

 * url: http://151.159.91.137:8080
 * username: USERNAME
 * password: PASSWORD

Reconfiguring Jenkins
=====================

To reconfigure Jenkins run the create_release_jobs.py script.

If you do not specify a custom workspace the release repositories will be cached under /tmp/repo-workspace-ROSDISTRO, so that you only have to update not clone the whole repo every time.

    scripts/create_release_jobs.py groovy --commit

If a package has been renamed or removed use the --delete option to remove jobs other than the ones just configured.

Triggering new builds
=====================

Once you have made a new release into a release repo, and updated the version number in the rosdistro.yaml file.  Run trigger_missing.py

    scripts/trigger_missing.py --sourcerpm-only groovy --commit

To retrigger all job generating Red Hat packages where the package does not yet exist run:

    scripts/trigger_missing.py groovy --commit
