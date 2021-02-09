import os
import json
import time
import requests
import hashlib

def post2slack(message):
    # Secret is passed as an ENV variable. Will throw an exception if not defined.
    url = "https://hooks.slack.com" + os.environ['SLACK_TEST']
    params = json.dumps({'text': message})
    headers = {"Content-type": "application/json", "Accept": "text/plain"}
    r = requests.post(url, data=params, headers=headers)
    ret = str(r.status_code) + " " + r.reason
    r.close()
    return ret

def unfrc(team):
    team = team.replace('frc','',1)
    if team == str(os.environ.get('FRC_TEAM', 0)):
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

    os.environ['TZ'] = os.environ.get('TARGET_TZ', 'GMT')
    time.tzset()

    message = ""
    body = payload
    if body['message_type'] == 'upcoming_match':
        predicted = time.strftime("%H:%M",time.localtime(body['message_data']['predicted_time']))
        scheduled = time.strftime("%H:%M",time.localtime(body['message_data']['scheduled_time']))
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
        first_match_time = time.strftime("%H:%M",time.localtime(body['message_data']['first_match_time']))
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
        message = "Verification code: " + body['message_data']
    elif body['message_type'] == 'ping':
        message += "Test ping from TBA: " + body['message_data']['desc']
    else:
        message += "Unprogrammed (yet) notification at "
        message += time.asctime(time.localtime(time.time())) + "\n"
        message += payload
    return message

def tba_to_slack(request):
    request_json = request.get_json()
    if request.args and 'payload' in request.args:
        payload = json.loads(request.args.get('payload'))
    elif request_json and 'message_type' in request_json:
        payload = request_json
    else:
        return f'Empty request. Nothing happened'

    tba_secret = os.environ.get('TBA_SECRET')
    if tba_secret:
        checksum = request.headers.get('X-Tba-Checksum')
        if hashlib.sha1('{}{}'.format(tba_secret.encode("utf-8"), payload.encode("utf-8"))).hexdigest() != checksum:
            print("checksum error happened")
            return ("checksum error happened", 501)

    return post2slack(parse_tba(payload))
