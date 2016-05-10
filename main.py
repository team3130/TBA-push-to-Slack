# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

import os
import json
import time
import hashlib
import logging
import webapp2
import httplib, urllib
import yaml

def post2slack(message):
    params = json.dumps({'text': message})
    headers = {"Content-type": "application/json", "Accept": "text/plain"}
    conn = httplib.HTTPSConnection(config['webhook_hostname'])
    conn.request("POST", config['webhook_request'], params, headers)
    response = conn.getresponse()
    ret = str(response.status) + " " + response.reason + "<br>\n"
    ret += response.read()
    conn.close()
    return ret

def unfrc(str):
    return str.replace('frc','',1)

def parse_tba(payload):
    message = ""
    body = json.loads(payload)
    if body['message_type'] == 'upcoming_match':
        message += "Upcoming match red[ "
        count = 0
        for team in body['message_data']['team_keys']:
            message += unfrc(team) +" "
            count += 1
            if count == 3:
              message += "] blue[ "
        predicted = time.strftime("%H:%M",time.localtime(body['message_data']['predicted_time']-(3600*5)))
        scheduled = time.strftime("%H:%M",time.localtime(body['message_data']['scheduled_time']-(3600*5)))
        message += "] at "+predicted+" (scheduled: "+scheduled+") "
        message += body['message_data']['match_key']
    elif body['message_type'] == 'match_score':
        message += "Match results: "
        for alliance in ['blue','red']:
            message += alliance + " [ "
            for team in body['message_data']['match']['alliances'][alliance]['teams']:
                message += unfrc(team) +" "
            message += "] "
            message += "scored " + str(body['message_data']['match']['alliances'][alliance]['score'])
            message += "; "
    else:
        message += "TBA is trying to tell us something about " + body['message_type']
        message += " at " + time.asctime(time.localtime())
    return message

class IncomingHandler(webapp2.RequestHandler):
    def post(self):
        payload = self.request.body

        if config.get('tba_secret'):
            checksum = self.request.headers.get('X-Tba-Checksum')
            if hashlib.sha1('{}{}'.format(config.get('tba_secret'), payload)).hexdigest() != checksum:
                self.response.write("checksum error happened")
                print "checksum error happened"
                return

        if payload.startswith("payload="):
            payload = payload.replace("payload=","",1)
            payload = urllib.unquote_plus(payload)
        self.response.write(post2slack(parse_tba(payload)))

class MainHandler(webapp2.RequestHandler):
    def get(self):
        message = '<form action="/hook" method="post"><textarea name="payload"></textarea><input type="submit" value="Submit"></form>'
        self.response.write(message)

with open("secrets.yaml", 'r') as stream:
    try:
        config = yaml.load(stream)
    except yaml.YAMLError as exc:
        print(exc)

app = webapp2.WSGIApplication([
    ('/hook', IncomingHandler),
    ('/', MainHandler),
], debug=True)

