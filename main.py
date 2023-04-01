import os
import json
import time
import requests
import hashlib

def post2slack(message):
    # Secret is passed as an ENV variable. Will throw an exception if not defined.
    url = "https://hooks.slack.com" + os.environ['SLACK_PROD']
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

    body = payload
    message_data = body['message_data']
    message_type = body['message_type']
    message = ""
    if message_type == 'upcoming_match':
        message += "Upcoming match"
        if 'predicted_time' in message_data:
            predicted = time.strftime("%H:%M",time.localtime(message_data['predicted_time']))
            message += " at " + predicted + "\n"
        if 'scheduled_time' in message_data:
            scheduled = time.strftime("%H:%M",time.localtime(message_data['scheduled_time']))
            message += "Originally scheduled " + scheduled + "\n"
        if 'team_keys' in message_data:
            message += "[ "
            count = 0
            for team in message_data['team_keys']:
                message += unfrc(team) +" "
                count += 1
                if count == 3:
                    message += "] vs. [ "
        message += "]\nMatch " + message_data['match_key']
        message += ' at "' + message_data["event_name"] + '"'

    elif message_type == 'match_score':
        message += "Match " + str(message_data['match']['match_number']) + " results:\n"
        for alliance in ['blue','red']:
            alliance_data = message_data['match']['alliances'][alliance]
            message += alliance + " [ "
            for team in alliance_data['team_keys']:
                message += unfrc(team) +" "
            message += "] "
            message += "scored " + str(alliance_data['score'])
            message += "\n"

    elif message_type == 'schedule_updated':
        message += "A match added "
        if 'first_match_time' in message_data:
            first_match_time = time.strftime("%H:%M",time.localtime(message_data['first_match_time']))
            message += first_match_time
        message += "\nto " + '"' + message_data["event_name"] + '"'

    elif message_type == 'starting_comp_level':
        message += "Competition started. Level: " + COMP_LEVELS_VERBOSE_FULL[message_data['comp_level']]

    elif message_type == 'alliance_selection':
        message += "Alliances selected for " + message_data['event']['start_date'] + "\n"
        count = 1
        for alliance in message_data['event']['alliances']:
            message += str(count) + ": "
            message += ', '.join(unfrc(x) for x in alliance['picks'])
            message += "\n"
            count += 1

    elif message_type == 'match_video':
        event_name = message_data['event_name']
        match_key = message_data['match']['key']
        message += f"A match video for {match_key} of {event_name} has been uploaded"
        if "videos" in message_data['match']:
            for video in message_data['match']['videos']:
                if video['type'] == "youtube":
                    video_url = 'https://youtube.com/watch?v=' + video['key']
                    message += f'<a href="{video_url}">Youtube</a>'

    elif message_type == 'verification':
        print("Verification code: ", message_data)
        message = "Verification code: " + message_data

    elif message_type == 'ping':
        message += "Test ping from TBA: " + message_data['desc']

    else:
        message += "Unprogrammed (yet) notification at "
        message += time.asctime(time.localtime(time.time())) + "\n"
        message += message_type

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
