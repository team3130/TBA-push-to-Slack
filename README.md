# TBA-push-to-Slack
A Google AppEngine code to receive push notifications from The Blue Alliance and post them on Slack via push notifications as well.

# Google Cloud Functions
Starting 2021 this code got rewritten to run on GCS Cloud Functions rather than on GCS App Engine.
Functions is a simpler, one function focused, microservices kind of platform.
No need to deploy a whole App Engine to process simple push requests from TBA and perform 
another own push request to Slack.

If you are familiar with old good AWS Lambda Functions. GC Functions is pretty much the same thing.

# Setup

Deploy the content of main.py as a Google Cloud Function using Python3 (tested with Python 3.7).
Set the "entryPoint" as "tba_to_slack".
Then configure the VARIABLES as described below. Then go to your account at TBA and point your webhook
to the Trigger URL of the Function you just deployed.

# Configuration
## Two secret variables
* SLACK_TEST: "/services/A99A9AAA9/*DUMMY*555/d1Fake8-Fake-Fake-xyzzz"
* SLACK_PROD: "/services/A99A9AAA9/*DUMMY*555/d1Fake8-Fake-Fake-xyzzz"

## The secret that you have between you and TheBlueAlliance
* TBA_SECRET: "ERRORS 3130 are awesome"

## The time-zone in which the events time should be displayed
* TARGET_TZ: US/Central

## Your team number
* FRC_TEAM: 3130