# Copyright (C) 2006-2009 Citrix Systems Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; version 2.1 only. with the special
# exception on linking described in file LICENSE.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.

import SOAPpy
from SOAPpy import Types
import re, os.path, base64, urllib, urllib2
import xml.dom.minidom
import array
import time

_jira = None

class Jira:

    StatusResolved = 5
    STATUS = {}
    RESOLUTION = {}
    TYPES = {}
    PRIORITIES = {}

    def __init__(self,url,username,password):
        global _jira
        _jira = self

        self.url = url
        self.username = username
        self.password = password

        # Open JIRA connection and login
        self.jira = SOAPpy.WSDL.Proxy(
                        "%s/rpc/soap/jirasoapservice-v2?wsdl" % (url))
        if self.jira:
            self.auth = self.jira.login(username,password)
        else:
            raise Exception("Unable to connect to Jira")

        # Get statuses from Jira...
        statuses = self.jira.getStatuses(self.auth)
        for s in statuses:
            self.STATUS[s.id] = s.name
        # Get resolutions from Jira...
        resolutions = self.jira.getResolutions(self.auth)
        for r in resolutions:
            self.RESOLUTION[r.id] = r.name
        # Get types rrom Jira...
        types = self.jira.getIssueTypes(self.auth) + self.jira.getSubTaskIssueTypes(self.auth)
        for t in types:
            self.TYPES[t.id] = t.name
        # Get priorities from Jira...
        prios = self.jira.getPriorities(self.auth)
        for p in prios:
            self.PRIORITIES[p.id] = p.name

    def getUserFullName(self, user):
        return self.jira.getUser(self.auth, user)['fullname']

    def createIssue(self,project,summary,type,priority,description=None,
                    affectsVersions=None,assignee="-1",components=None,
                    customFields=None,environment=None):

        # Process priority and type
        for p in self.PRIORITIES:
            if self.PRIORITIES[p] == priority:
                priority = p
                break
        for t in self.TYPES:
            if self.TYPES[t] == type:
                type = t
                break

        fields = {'project': project, 'summary': summary, 'priority': priority, 'type': type, 'assignee': assignee}
        if description:
            fields['description'] = description
        if affectsVersions:
            fields['affectsVersions'] = affectsVersions
        if components:
            fields['components'] = components
        if environment:
            fields['environment'] = environment
        ri = JiraIssue(self.jira.createIssue(self.auth,fields))
        if customFields:
            for cf in customFields:
                ri.setCustomField(cf[0],cf[1],update=False)
            ri.updateCustomFields()
        return ri

    def deleteIssue(self,key):
        try:
            self.jira.deleteIssue(self.auth,key)
        except:
            raise Exception("Issue %s not found" % (key))

    def getIssue(self,key):
        try:
            ri = self.jira.getIssue(self.auth,key)
            return JiraIssue(ri)
        except:
            raise Exception("Issue %s not found" % (key))

    def getIssuesFromFilter(self,filterId):
        try:
            ris = self.jira.getIssuesFromFilter(self.auth,filterId);
            return [ JiraIssue(i) for i in ris ]
        except:
            raise Exception("Filter ID not found")

    def getProject(self,projectKey):
        """Check the project exists, if so, return it."""
        try:
            rp = self.jira.getProjectByKey(self.auth,projectKey)
            return JiraProject(rp, projectKey)
        except:
            raise Exception("Project not found")

    def addVersionToProject(self,projectKey,version):
        """Add a version to a project, given the project key string."""
        rv = self.jira.addVersion(self.auth, projectKey, {'name': version})
        return rv['id']

    def addFixedVersion(self, versionName, ticket, comment, force=False):
        """Given an ticket number, mark its issue Fixed in the named version.

        If the issue's status is not Resolved, don't add the version to FixedVersions.
        The optional force parameter overrides this. The comment is always added.
        """
        issue = self.getIssue(ticket)
        if force or issue.status == Jira.StatusResolved:
            issue.addFixedVersion(versionName)
        issue.addComment(comment)

    def getIssuesFromFilterName(self, filterName):
        """Given a filter name, return a list of JiraIssue objects that match"""
        filter = self.getFilter(filterName)
        issues = filter.getIssues()

        return issues

    def getGroup(self, groupName):
        """Check the group exists, if so, return it."""
        try:
            rg = self.jira.getGroup(self.auth, groupName)
            return JiraGroup(rg, groupName)
        except:
            raise Exception("Group not found")

    def getGroupUsers(self, groupName):
        """Return the users of the group with passed name."""
        group = self.getGroup(groupName)
        return group.getUsers()

    def getSavedFilters(self):
        """Return list of filters this login can see"""
        remoteFilters = self.jira.getSavedFilters(self.auth)
        retFilters = []
        for filter in remoteFilters:
            retFilters.append(JiraFilter(filter))
        return retFilters

    def getFilter(self, filterName):
        """Return filter object for filter with passed name"""
        filters = self.getSavedFilters()
        retfilter = None
        for filter in filters:
            if filter.getName() == filterName:
                retfilter = filter
                break
        if retfilter == None:
            raise Exception("Filter not found")
        return retfilter

    def getFilterUrl(self, filterName):
        """Return a Url for the named filter"""
        filter = self.getFilter(filterName)
        return filter.getUrl()

class JiraObject:

    def __init__(self):
        global _jira

        self.Jira = _jira
        self.jira = _jira.jira
        self.auth = _jira.auth

class JiraProject(JiraObject):

    def __init__(self,RemoteProject,projectKey):
        JiraObject.__init__(self)

        self.RemoteProject = RemoteProject
        self.projectKey = projectKey

        # Parse the fields in the RemoteProject
        for k,v in RemoteProject.__dict__.items():
            self.__dict__[k] = v

    def archiveVersion(self,version,archive=True):
        self.jira.archiveVersion(self.auth,self.key,version,archive)

    def addVersion(self,version):
        self.jira.addVersion(self.auth, self.key, {'name': version})

    def getComponents(self):
        comps = self.jira.getComponents(self.auth, self.projectKey)
        return [ JiraComponent(c) for c in comps ]

class JiraComponent(JiraObject):

    def __init__(self,RemoteComponent):
        JiraObject.__init__(self)

        for k,v in RemoteComponent.__dict__.items():
            self.__dict__[k] = v

    def getName(self):
        return self.name

class JiraIssue(JiraObject):

    def __init__(self,RemoteIssue):
        JiraObject.__init__(self)

        self.RemoteIssue = RemoteIssue

        # Parse the fields in the RemoteIssue
        for k,v in RemoteIssue.__dict__.items():
            self.__dict__[k] = v

        # Get priorities
        prios = self.jira.getPriorities(self.auth)
        # Parse them
        self.priorities = {}
        for prio in prios:
            self.priorities[prio['name']] = prio['id']

        # Get custom fields
        fs = self.jira.getFieldsForEdit(self.auth,self.key)
        self.customFields = {}
        for f in fs:
            if f['id'].startswith("customfield_"):
                self.customFields[f['name']] = f['id']

    def __cmp__(self, other):
        return cmp(int(self.priority), int(other.priority))

    # Accessor methods

    def getCreated(self):
        return self.created

    def getStatus(self):
        return self.Jira.STATUS[self.status]

    def getResolution(self):
        if self.resolution == None:
            return None
        else:
            return self.Jira.RESOLUTION[self.resolution]

    def getSummary(self):
        return self.summary

    def getDescription(self):
        return self.description

    def getFixVersionNames(self):
        return [ i.name for i in self.fixVersions ]

    def getEnvironment(self):
        return self.environment

    def getComponents(self):
        return self.components

    def getAssignee(self):
        return self.assignee

    def getKey(self):
        return self.key

    def getPriority(self):
        return self.priority

    def getType(self):
        return self.Jira.TYPES[self.type]

    def getOriginalEstimate(self):
        u = "%s/plugins/servlet/xenrt/issue_getoriginalestimate" % self.Jira.url
        params = urllib.urlencode({"os_username": self.Jira.username,
                                   "os_password": self.Jira.password,
                                   "issue": self.key})
        f = urllib2.urlopen(u, params)
        data = f.read().strip()
        f.close()

        # data should be an integer:
        try:
            estimate = int(data)
        except:
            raise RuntimeError, "Error retrieving original estimate: got %s" % data

        return estimate

    def getComments(self):
        """Returns an array of dictionaries"""
        cs = self.jira.getComments(self.auth, self.key)
        return_cs = []
        for c in cs:
            return_cs.append(c._asdict())

        return return_cs

    def getCodeComplete(self):
        return self.getCustomTextField("Code Complete Date")

    def getFeatureCommitted(self):
        return self.getCustomTextField("Feature Committed")

    def getSpecification(self):
        return self.getCustomTextField("Specification")

    def getTestImpact(self):
        return self.getCustomTextField("Test Impact")

    def getDocImpact(self):
        return self.getCustomTextField("Documentation Impact")

    def getReleaseNotes(self):
        return self.getCustomTextField("Release Notes")


    def getChangeLog(self):
        clog = {}
        clog['contents'] = self.getCustomTextField("Change Log Entry")
        status = self.getCustomTextField("Change Log Visibility")
        if status == None:
            clog['status'] = "Internal"
        else:
            clog['status'] = status
        clog['category'] = self.getCustomTextField("Change Log Category")
        return clog

    def getCustomTextField(self,name):
        """Returns the specified custom field, assuming it is a free-form text field"""

        f = self.getCustomField(name)
        if f != None:
            return f[0]

    def getCustomField(self,name):
        """Returns the specified custom field"""

        if not self.customFields.has_key(name):
            return None

        cfs = self.customFieldValues
        for cf in cfs:
            if cf['customfieldId'] == self.customFields[name]:
                return cf['values']

    # Mutator methods

    def update(self,valuelist):
        """Update fields of an issue. Used internally and externally."""

        self.jira.updateIssue(self.auth, self.key, valuelist)

    def setSummary(self,summary):
        self.summary = summary
        self.update([{'id': 'summary','values': summary}])

    def setDescription(self,description):
        self.description = description
        self.update([{'id': 'description','values': description}])

    def setEnvironment(self,environment):
        self.environment = environment
        self.update([{'id': 'environment','values': environment}])

    def setPriority(self,priority):
        self.priority = priority
        self.update([{'id': 'priority','values': priority}])

    def setReporter(self,reporter):
        self.reporter = reporter
        self.update([{'id': 'reporter','values': reporter}])

    def setFeatureCommitted(self, committed):
        self.setCustomField("Feature Committed", committed)

    def addComment(self,comment):
        self.jira.addComment(self.auth, self.key, {'body': comment})

    def addSecureComment(self,comment,commentLevel):
        self.jira.addComment(self.auth, self.key, {'body': comment, 'roleLevel': commentLevel})

    def setCustomField(self,name,value,update=True):
        """Sets the specified custom field"""

        for cf in self.customFieldValues:
            if cf['customfieldId'] == self.customFields[name]:
                self.customFieldValues.remove(cf)
                break

        newcf = {'customfieldId': self.customFields[name], 'values': value}
        self.customFieldValues.append(newcf)

        if update:
            self.update([{'id': self.customFields[name], 'values': value}])

    def updateCustomFields(self):
        updates = []
        for cf in self.customFieldValues:
            updates.append({'id': cf['customfieldId'],
                            'values': cf['values']})

        self.update(updates)

    def addFixedVersion(self,versionName):
        # Find the version id. Doesn't Jira provide this?
        versions = self.jira.getVersions(self.auth, self.project)
        id = [v.id for v in versions if v.name == versionName][0]

        fixedin = map(lambda v: v['id'], self.fixVersions) + [id]
        self.update([{'id': 'fixVersions', 'values': fixedin }])

    def attachFile(self,path,name=None):
        """Attach file to this issue"""

        # check version of SOAPpy
        if SOAPpy.__version__ < '0.12.0':
            raise Exception("To use attachFile you must have SOAPpy v0.12.0 or later due to an API change.")

        # Get just the name of the file
        if name:
            filename = name
        else:
            filename = os.path.basename(path)

        # Read in the file
        f = file(path,"rb")
        data = f.read()
        f.close()
        data = base64.encodestring(data)

        # Make the call...
        self.jira.addAttachmentsToIssue(self.auth, self.key, [filename],
                                        [[data]])

    def linkIssue(self,linkTo,linkType):
        """Link this issue to another"""

        postURL = "%s/secure/LinkExistingIssue.jspa" % (self.Jira.url)
        postdic = urllib.urlencode({'os_username': self.Jira.username,
                                    'os_password': self.Jira.password,
                                    'id': self.id, 'linkDesc': linkType,
                                    'linkKey': linkTo})
        urllib2.urlopen(postURL,postdic)

    def getLinks(self):
        """Returns a dictionary of issue:linktype"""

        postURL = ("%s/si/jira.issueviews:issue-xml/%s/?os_username=%s&"
                  "os_password=%s" % (self.Jira.url,self.key,self.Jira.username,
                                      self.Jira.password))
        data = urllib2.urlopen(postURL).read()
        dom = xml.dom.minidom.parseString(data)
        ilts = dom.getElementsByTagName("issuelinktype")
        if len(ilts) < 1:
            return {}
        links = {}
        for ilt in ilts:
            for cn in ilt.childNodes:
                if cn.nodeName == "outwardlinks" or \
                   cn.nodeName == "inwardlinks":
                    desc = cn.attributes['description'].value
                    for cnn in cn.childNodes:
                        if cnn.nodeName == "issuelink":
                            for cnnn in cnn.childNodes:
                                if cnnn.nodeName == "issuekey":
                                    links[cnnn.childNodes[0].data] = desc
        return links

    def deleteLink(self, issue):
        """Deletes all links between this issue and the specified issue"""

        postURL = ("%s/si/jira.issueviews:issue-xml/%s/?os_username=%s&"
                  "os_password=%s" % (self.Jira.url,self.key,self.Jira.username,
                                      self.Jira.password))
        data = urllib2.urlopen(postURL).read()
        dom = xml.dom.minidom.parseString(data)
        key = dom.getElementsByTagName("key")[0].getAttribute("id")
        ilts = dom.getElementsByTagName("issuelinktype")
        deleted = False
        for ilt in ilts:
            linktype = ilt.getAttribute("id")
            for cn in ilt.childNodes:
                if cn.nodeName == "outwardlinks" or \
                   cn.nodeName == "inwardlinks":
                    desc = cn.attributes['description'].value
                    for cnn in cn.childNodes:
                        if cnn.nodeName == "issuelink":
                            for cnnn in cnn.childNodes:
                                if cnnn.nodeName == "issuekey":
                                    if cnnn.childNodes[0].data == issue:
                                        id = cnnn.getAttribute("id")
                                        self._deleteLink(key, id, linktype)
                                        deleted = True
        if not deleted:
            raise Exception("Issue not currently linked")

    def _deleteLink(self, id, destId, linkType):
        """Deletes the specified link"""

        postURL = ("%s/secure/DeleteLink.jspa?id=%s&destId=%s&linkType=%s&"
                   "confirm=true&os_username=%s&os_password=%s" % 
                   (self.Jira.url,id,destId,linkType,self.Jira.username,
                    self.Jira.password))
        urllib2.urlopen(postURL)

    def getParent(self):
        """Return the key of the parent ticket if this is a sub-task. Returns
        None if this is not a sub-task."""
        postURL = ("%s/si/jira.issueviews:issue-xml/%s/?os_username=%s&"
                  "os_password=%s" % (self.Jira.url,self.key,self.Jira.username,
                                      self.Jira.password))
        data = urllib2.urlopen(postURL).read()
        dom = xml.dom.minidom.parseString(data)
        ps = dom.getElementsByTagName("parent")
        if len(ps) == 0:
            return None
        if len(ps) > 1:
            raise Exception("Multiple 'parent' nodes found for %s" % (self.key))
        return ps[0].childNodes[0].data

    def getChildren(self):
        """Return a list of the keys of the child sub-task tickets if any. Returns
        empty list if this has no sub-tasks."""
        postURL = ("%s/si/jira.issueviews:issue-xml/%s/?os_username=%s&"
                  "os_password=%s" % (self.Jira.url,self.key,self.Jira.username,
                                      self.Jira.password))
        data = urllib2.urlopen(postURL).read()
        dom = xml.dom.minidom.parseString(data)
        subtasks_tags = dom.getElementsByTagName("subtasks")
        if len(subtasks_tags) == 0:
            return []
        subtasks = []
        for st in subtasks_tags:
            for cn in st.childNodes:
                if cn.nodeName == "subtask":
                    subtasks.append(cn.childNodes[0].data)
        return subtasks

    def copyAttachmentsTo(self, destination):
        """Copy attachments from the ticket to the destination dir"""
        if not os.path.isdir(destination):
            raise Exception("Destination must be a directory")

        # Get the attachment details
        attachments = self.jira.getAttachmentsFromIssue(self.auth,self.key)

        # Build authentication string
        auth = "os_username=%s&os_password=%s" % (self.Jira.username,
                                                  self.Jira.password)

        # Grab each attachment
        for a in attachments:
            url = "%s/secure/attachment/%s/%s?%s" % (self.Jira.url,a.id,
                                                     urllib.quote(a.filename),
                                                     auth)
            data = urllib2.urlopen(url).read()
            f = file("%s/%s" % (destination,a.filename),"w")
            f.write(data)
            f.close()

    def getReporter(self):
        return self.reporter

    def accept(self):
        self.Jira.jira.progressWorkflowAction(self.Jira.auth, self.key, '731',
                                              [{'id': 'priority', 'values': [self.getPriority()]}])

    def resolve(self, resolution):
        """Resolve the issue with the specified resolution"""

        rid = None
        for r in self.Jira.RESOLUTION:
            if self.Jira.RESOLUTION[r] == resolution:
                rid = r
                break
        if not rid:
            raise Exception("Unknown resolution %s" % (resolution))

        status = self.getStatus()
        if status == "New":
            self.acceptWorkflow()
            self.resolveWorkflow('721', rid)
        elif status == "Reopened" or status == "In Progress":
            self.resolveWorkflow('5', rid)
        elif status == "Resolved":
            raise Exception("Issue %s already resolved." % self.key)
        raise Exception("Cannot resolve issue %s. Wrong status: %s" % (self.key, status))

    def acceptWorkflow(self):
        self.Jira.jira.progressWorkflowAction(self.Jira.auth, self.key, '731',
                                              [{'id': 'priority', 'values': [self.getPriority()]}])        

    def resolveWorkflow(self, action, rid):
        self.Jira.jira.progressWorkflowAction(self.Jira.auth, self.key, action,
                                              [{'id': 'resolution', 'values': [str(rid)]}])

class JiraGroup(JiraObject):

    def __init__(self, remoteGroup, groupName):
        JiraObject.__init__(self)

        self.RemoteGroup = remoteGroup
        self.groupName = groupName

        # Parse the fields in the RemoteGroup
        for k,v in remoteGroup.__dict__.items():
            self.__dict__[k] = v

    def getUsers(self):
        """Return the users of the group"""
        users = self.RemoteGroup.users
        retusers = []
        for user in users:
            retusers.append(JiraUser(user))
        return retusers

class JiraUser(JiraObject):

    def __init__(self, RemoteUser):
        JiraObject.__init__(self)

        self.RemoteUser = RemoteUser

        # Parse the fields in the Remoteuser
        for k,v in RemoteUser.__dict__.items():
            self.__dict__[k] = v

class JiraFilter(JiraObject):

    def __init__(self, RemoteFilter):
        JiraObject.__init__(self)

        self.RemoteFilter = RemoteFilter

        # Parse the fields in the Remoteuser
        for k,v in RemoteFilter.__dict__.items():
            self.__dict__[k] = v

    def getIssues(self):
        """Return the issues seen using this filter"""
        issues = self.jira.getIssuesFromFilter(self.auth, self.id)
        return [ JiraIssue(i) for i in issues ]

    def getName(self):
        return self.name

    def getUrl(self):
        url = "%s/secure/IssueNavigator.jspa?mode=hide&requestId=%s" % (self.Jira.url,self.id)
        return url
