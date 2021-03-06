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

def unfrc(team):
    team = team.replace('frc','',1)
    if team == str(config.get('frc_team', 0)):
        team = '*' + team + '*'
    return team

def parse_tba(payload):
    COMP_LEVELS_VERBOSE_FULL = {
        "qm": "Qualification",
        "ef": "Octo-finals",
        "qf": "Quarterfinals",
        "sf": "Semifinals",
        "f": "Finals",
    }
    tz_offset = config.get('tz_offset', 0)
    message = ""
    body = json.loads(payload)
    if body['message_type'] == 'upcoming_match':
        predicted = time.strftime("%H:%M",time.gmtime(body['message_data']['predicted_time']-tz_offset))
        scheduled = time.strftime("%H:%M",time.gmtime(body['message_data']['scheduled_time']-tz_offset))
        message += "Upcoming match at " + predicted + "\n[ "
        count = 0
        for team in body['message_data']['team_keys']:
            message += unfrc(team) +" "
            count += 1
            if count == 3:
              message += "] vs. [ "
        message += "]\nsched: " + scheduled + ", key: "
        message += body['message_data']['match_key'] + "\n"
        message += '"' + body['message_data']["event_name"] + '"'
    elif body['message_type'] == 'match_score':
        message += "Match " + str(body['message_data']['match']['match_number']) + " results: \n"
        for alliance in ['blue','red']:
            message += alliance + " [ "
            for team in body['message_data']['match']['alliances'][alliance]['teams']:
                message += unfrc(team) +" "
            message += "] "
            message += "scored " + str(body['message_data']['match']['alliances'][alliance]['score'])
            message += "\n"
    elif body['message_type'] == 'schedule_updated':
        first_match_time = time.strftime("%H:%M",time.gmtime(body['message_data']['first_match_time']-tz_offset))
        message += "A match added " + first_match_time + ", nothing major."
    elif body['message_type'] == 'starting_comp_level':
        message += "Competition started. Level: " + COMP_LEVELS_VERBOSE_FULL[body['message_data']['comp_level']]
    elif body['message_type'] == 'alliance_selection':
        message += "Alliances selected for " + body['message_data']['event']['start_date'] + "\n"
        count = 1
        for alliance in body['message_data']['event']['alliances']:
            message += str(count) + ": "
            message += ', '.join(unfrc(x) for x in alliance['picks'])
            message += "\n"
            count += 1
    elif body['message_type'] == 'verification':
        print("Verification code: ", body['message_data'])
    elif body['message_type'] == 'ping':
        message += "Test ping from TBA: " + body['message_data']['desc']
    else:
        message += "Unprogrammed (yet) notification at "
        message += time.asctime(time.gmtime(time.time())) + " UTC\n"
        message += payload
    return message

class IncomingHandler(webapp2.RequestHandler):
    def post(self):
        payload = self.request.body

        if config.get('tba_secret'):
            checksum = self.request.headers.get('X-Tba-Checksum')
            if hashlib.sha1('{}{}'.format(config.get('tba_secret'), payload)).hexdigest() != checksum:
                self.response.write("checksum error happened")
                print("checksum error happened")
                return

        if payload.startswith("payload="):
            payload = payload.replace("payload=","",1)
            payload = urllib.unquote_plus(payload)
        self.response.write(post2slack(parse_tba(payload)))

class MainHandler(webapp2.RequestHandler):
    def get(self):
        message = 'Hello, human...<form action="/hook" method="post"><textarea name="payload"></textarea><input type="submit" value="Submit"></form>'
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

