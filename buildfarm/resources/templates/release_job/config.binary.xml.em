<?xml version='1.0' encoding='UTF-8'?>
<project>
  <actions/>
  <description>Generated job to create binary debs for wet package "@(PACKAGE)". DO NOT EDIT BY HAND. Generated by catkin-debs/scripts/create_release_jobs.py for @(USERNAME) at @(TIMESTAMP)</description>
  <logRotator>
    <daysToKeep>30</daysToKeep>
    <numToKeep>10</numToKeep>
    <artifactDaysToKeep>30</artifactDaysToKeep>
    <artifactNumToKeep>-1</artifactNumToKeep>
  </logRotator>
  <keepDependencies>false</keepDependencies>
  <properties/>
  <scm class="hudson.scm.NullSCM"/>
  <assignedNode>debbuild</assignedNode>
  <canRoam>false</canRoam>
  <disabled>false</disabled>
  <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
  <blockBuildWhenUpstreamBuilding>true</blockBuildWhenUpstreamBuilding>
  <triggers class="vector"/>
  <concurrentBuild>false</concurrentBuild>
  <builders>
    <hudson.plugins.groovy.SystemGroovy plugin="groovy@@1.12">
      <scriptSource class="hudson.plugins.groovy.StringScriptSource">
        <command>
// VERFIY THAT NO UPSTREAM PROJECT IS BROKEN
import hudson.model.Result

println ""
println "Verify that no upstream project is broken"
println ""

project = Thread.currentThread().executable.project

for (upstream in project.getUpstreamProjects()) {
	abort = upstream.getNextBuildNumber() == 1

	if (!abort) {
		lb = upstream.getLastBuild()
		if (!lb) continue

		r = lb.getResult()
		if (!r) continue

		abort = r.isWorseOrEqualTo(Result.FAILURE)
	}

	if (abort) {
		println "Aborting build since upstream project '" + upstream.name + "' is broken"
		println ""
		throw new InterruptedException()
	}
}

println "All upstream projects are (un)stable"
println ""
</command>
      </scriptSource>
      <bindings/>
      <classpath/>
    </hudson.plugins.groovy.SystemGroovy>
    <hudson.tasks.Shell>
      <command>@(COMMAND)</command>
    </hudson.tasks.Shell>
    <hudson.plugins.groovy.SystemGroovy plugin="groovy@@1.12">
      <scriptSource class="hudson.plugins.groovy.StringScriptSource">
        <command>
// CHECK FOR "HASH SUM MISMATCH" AND RETRIGGER JOB
// only triggered when previous build step was successful
import java.io.BufferedReader
import java.util.regex.Matcher
import java.util.regex.Pattern

import hudson.model.Cause
import hudson.model.Result

println ""
println "Check for 'Hash Sum mismatch'"
println ""

build = Thread.currentThread().executable

// search build output for hash sum mismatch
r = build.getLogReader()
br = new BufferedReader(r)
pattern = Pattern.compile(&quot;.*W: Failed to fetch .* Hash Sum mismatch.*&quot;)
def line
while ((line = br.readLine()) != null) {
	if (pattern.matcher(line).matches()) {
		println "Aborting build due to 'hash sum mismatch'. Immediately rescheduling new build..."
		println ""
		build.project.scheduleBuild(new Cause.UserIdCause())
		throw new InterruptedException()
	}
}
println "Pattern not found in build log"
println ""
</command>
      </scriptSource>
      <bindings/>
      <classpath/>
    </hudson.plugins.groovy.SystemGroovy>
  </builders>
  <publishers>
    <org.jvnet.hudson.plugins.groovypostbuild.GroovyPostbuildRecorder plugin="groovy-postbuild@@1.8">
      <groovyScript>
// CHECK FOR VARIOUS REASONS TO RETRIGGER JOB
// also triggered when a build step has failed
import hudson.model.Cause
if (manager.logContains(&quot;.*W: Failed to fetch .* Hash Sum mismatch.*&quot;)) {
	manager.addInfoBadge("Log contains 'Hash Sum mismatch' - scheduled new build...")
	manager.build.project.scheduleBuild(new Cause.UserIdCause())
}
if (manager.logContains(&quot;.*The lock file '/var/www/repos/building/db/lockfile' already exists.*&quot;)) {
	manager.addInfoBadge("Log contains 'building/db/lockfile already exists' - scheduled new build...")
	manager.build.project.scheduleBuild(new Cause.UserIdCause())
}
if (manager.logContains(&quot;.*E: Could not get lock /var/lib/dpkg/lock - open \\(11: Resource temporarily unavailable\\).*&quot;)) {
	manager.addInfoBadge("Log contains 'dpkg/lock temporary unavailable' - scheduled new build...")
	manager.build.project.scheduleBuild(new Cause.UserIdCause())
}
if (manager.logContains(&quot;.*ERROR: cannot download default sources list from:.*&quot;)) {
	manager.addInfoBadge("Log contains 'cannot download default sources list' - scheduled new build...")
	manager.build.project.scheduleBuild(new Cause.UserIdCause())
}
</groovyScript>
      <behavior>0</behavior>
    </org.jvnet.hudson.plugins.groovypostbuild.GroovyPostbuildRecorder>
    <org.jvnet.hudson.plugins.groovypostbuild.GroovyPostbuildRecorder plugin="groovy-postbuild@@1.8">
      <groovyScript>
import java.io.BufferedReader
import java.util.regex.Matcher
import java.util.regex.Pattern

import hudson.model.Result

class Group {
	String label
	String badge
	String summary_icon
	Boolean mark_unstable = true
	List match_extractors = []
	List matched_items = []
	Group(String label, String badge, String summary_icon) {
		this.label = label
		this.badge = badge
		this.summary_icon = summary_icon
	}
}

// define notification groups
warnings_group = new Group(label=&quot;Warnings&quot;, badge=&quot;warning.gif&quot;, summary_icon=&quot;warning.png&quot;)
deprecations_group = new Group(label=&quot;Deprecations&quot;, badge=&quot;info.gif&quot;, summary_icon=&quot;star.png&quot;)

class MatchExtractor {
	Pattern pattern
	int next_lines
	Boolean skip_first_line
	MatchExtractor(Pattern pattern) {
		this.pattern = pattern
		this.next_lines = 0
		this.skip_first_line = false
	}
	MatchExtractor(Pattern pattern, int next_lines) {
		this.pattern = pattern
		this.next_lines = next_lines
		this.skip_first_line = false
	}
	MatchExtractor(Pattern pattern, int next_lines, Boolean skip_first_line) {
		this.pattern = pattern
		this.next_lines = next_lines
		this.skip_first_line = skip_first_line
	}
}

// define patterns and extraction parameters
// catkin_pkg warnings for invalid package.xml files
warnings_group.match_extractors.add(new MatchExtractor(pattern=Pattern.compile(&quot;WARNING\\(s\\) in .*:&quot;), next_lines=1, skip_first_line=true))
// custom catkin deprecation messages
deprecations_group.match_extractors.add(new MatchExtractor(pattern=Pattern.compile(&quot;.*\\) is deprecated.*&quot;)))
// c++ compiler warning for usage of a deprecated function
deprecations_group.match_extractors.add(new MatchExtractor(pattern=Pattern.compile(&quot;.* is deprecated \\(declared at .*&quot;)))


groups = [warnings_group, deprecations_group]

// search build output and extract found matches
r = manager.build.getLogReader()
br = new BufferedReader(r)
def line
while ((line = br.readLine()) != null) {
	for (group in groups) {
		for (me in group.match_extractors) {
			if (me.pattern.matcher(line).matches()) {
				data = []
				if (!me.skip_first_line) data.add(line)
				if (me.next_lines) {
					for (i in 1..me.next_lines) {
						line = br.readLine()
						if (line == null) break
						data.add(line)
					}
				}
				group.matched_items.add(data.join(&quot;&lt;br/&gt;&quot;))
			}
		}
	}
}

// add badges and summaries for matches
mark_unstable = false
for (group in groups) {
	if (group.matched_items) {
		manager.addBadge(group.badge, &quot;&quot;)
		summary_text = &quot;&quot;
		if (group.label) {
			summary_text += group.label + &quot;:&quot;
		}
		summary_text += &quot;&lt;ul&gt;&quot;
		for(i in group.matched_items) {
			summary_text += &quot;&lt;li&gt;&quot; + i + &quot;&lt;/li&gt;&quot;
		}
		summary_text += &quot;&lt;/ul&gt;&quot;
		summary = manager.createSummary(group.summary_icon)
		summary.appendText(summary_text, false)
		if (group.mark_unstable) mark_unstable = true
	}
}

// mark build as unstable
if (mark_unstable) {
	if (manager.build.getResult().isBetterThan(Result.UNSTABLE)) {
		manager.build.setResult(Result.UNSTABLE)
	}
}
</groovyScript>
      <behavior>0</behavior>
    </org.jvnet.hudson.plugins.groovypostbuild.GroovyPostbuildRecorder>
    <hudson.tasks.BuildTrigger>
      <childProjects>@(','.join(CHILD_PROJECTS))</childProjects>
      <threshold>
        <name>UNSTABLE</name>
        <ordinal>1</ordinal>
        <color>YELLOW</color>
      </threshold>
    </hudson.tasks.BuildTrigger>
    <hudson.plugins.descriptionsetter.DescriptionSetterPublisher>
      <regexp>^package name [^\s]+ version ([^\s]+)$</regexp>
      <regexpForFailed/>
      <setForMatrix>false</setForMatrix>
    </hudson.plugins.descriptionsetter.DescriptionSetterPublisher>
    <hudson.tasks.Mailer>
      <recipients>@(NOTIFICATION_EMAIL)</recipients>
      <dontNotifyEveryUnstableBuild>false</dontNotifyEveryUnstableBuild>
      <sendToIndividuals>false</sendToIndividuals>
    </hudson.tasks.Mailer>
  </publishers>
  <buildWrappers/>
</project>
