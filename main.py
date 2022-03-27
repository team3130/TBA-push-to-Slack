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
    ret = (r.reason, r.status_code)
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
        message += "]\nMatch " + body['message_data']['match_key']
        message += " sched " + scheduled + "\n"
        message += '"' + body['message_data']["event_name"] + '"'

    elif body['message_type'] == 'match_score':
        message += "Match " + str(body['message_data']['match']['match_number']) + " results: \n"
        for alliance in ['blue','red']:
            message += alliance + " [ "
            for team in body['message_data']['match']['alliances'][alliance]['team_keys']:
                message += unfrc(team) +" "
            message += "] "
            message += "scored " + str(body['message_data']['match']['alliances'][alliance]['score'])
            message += "\n"

    elif body['message_type'] == 'schedule_updated':
        first_match_time = time.strftime("%H:%M",time.localtime(body['message_data']['first_match_time']))
        message += "A match added " + first_match_time

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

    elif body['message_type'] == 'match_video':
        event_name = body['message_data']['event_name']
        match_key = body['message_data']['match']['key']
        message += f"A match video for {match_key} of {event_name} has been uploaded"
        if "videos" in body['message_data']['match']:
            if body['message_data']['match']['videos']['type'] == "youtube":
                video_url = 'https://youtube.com/watch?v=' + body['message_data']['match']['videos']['key']
                message += f'<a href="{video_url}">Youtube</a>'

    elif body['message_type'] == 'verification':
        print("Verification code: ", body['message_data'])
        message = "Verification code: " + body['message_data']

    elif body['message_type'] == 'ping':
        message += "Test ping from TBA: " + body['message_data']['desc']

    else:
        message += "Unprogrammed (yet) notification at "
        message += time.asctime(time.localtime(time.time())) + "\n"
        message += body['message_type']

    return message

def tba_to_slack(request):
    strdata = None
    payload = None
    message_type = "Unknown"
    if request.args and 'payload' in request.args:
        # So we can use a HTML form for debugging
        strdata = request.args.get('payload')
        payload = json.loads(strdata)
    else:
        # The body must be a JSON
        request_json = request.get_json()
        if request_json and 'message_type' in request_json:
            strdata = request.data
            payload = request_json
        else:
            # Otherwise no idea what to do
            return f'Empty request. Nothing happened'

    tba_secret = os.environ.get('TBA_SECRET')
    if tba_secret:
        tba_checksum = request.headers.get('X-TBA-Checksum')
        ch = hashlib.sha1()
        ch.update(tba_secret.encode('UTF-8'))
        ch.update(strdata)
        checksum = ch.hexdigest()
        if tba_checksum != checksum:
            print(f"""
    Checksum error happened
    Request data: {strdata}
    Checksum: {checksum}""")
            return ("checksum error happened", 501)

    try:
        message_type = payload['message_type']
        print(f"Processing {message_type}")
        message = parse_tba(payload)
    except Exception as e:
        print(f"Exception {e}\n with input data: \n{strdata}")
        message = f"Something about {message_type}. Please check TBA."

    return post2slack(message)
