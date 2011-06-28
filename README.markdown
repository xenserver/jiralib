# Pull Request Manager

## Original authors

* Alex Brett <alex@xensource.com>
* Anil Madhavapeddy <anil@xensource.com>

## Description

A Python library for SOAP interaction with
[JIRA](http://www.atlassian.com/software/jira/).

## Usage

Common usage pattern includes:

1. creating a `Jira` object;
2. fetching an issue with it;
3. manipulating the issue through available methods.

For example:

    j = jira.Jira("http://my-jira-url/", "my-username", "my-password")
    i = j.getIssue("CA-5555")
    i.addComment("This is a test comment.")

## Feedback and Contributions

Feedback and contributions are welcome. Please submit contributions
via GitHub pull requests.
