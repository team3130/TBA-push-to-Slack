import os
import time
import requests
import json

def hello_world(request):
    """Responds to any HTTP request.

    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    request_json = request.get_json()
    slack_host = "https://hooks.slack.com"
    headers = {"Content-type": "application/json", "Accept": "text/plain"}
    secret = os.environ.get('SLACK_TEST', 'Specified environment variable is not set.')
    url = slack_host + secret
    r = requests.post(url, data=json.dumps({'text':'Test from G-Cloud Functions'}), headers=headers)
    os.environ['TZ'] = os.environ.get('TARGET_TZ', 'US/Central')
    time.tzset()
    if request.args and 'message' in request.args:
        return 'Got args: ' + request.args.get('message') + time.strftime(" at %H:%M",time.localtime())
    elif request_json and 'message' in request_json:
        return 'Got json: ' + request_json['message']
    else:
        return f'Hello World!'

