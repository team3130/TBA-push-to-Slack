import os
import json
import time
import hashlib
from slack_sdk.webhook import WebhookClient
from slack_sdk.errors import SlackApiError


def unfrc(team):
    # TBA uses 'frcNNNN' format for the team names, we drop 'frc'
    team = team.replace('frc','',1)
    if team == str(os.environ.get('FRC_TEAM', 0)):
        # if this is our team we make it bold (Markup)
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

    message_data = payload['message_data']
    message_type = payload['message_type']
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
        message += ' at ' + message_data["event_name"]
        if 'webcast' in message_data:
            webcast = message_data['webcast']
            webcast_type = webcast['type']
            webcast_channel = webcast['channel']
            if webcast_type == "twitch":
                message += f"\nCast: www.twitch.tv/{webcast_channel}"

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
        message += "\nto " + message_data["event_name"]

    elif message_type == 'starting_comp_level':
        message += "Competition started. Level: " + COMP_LEVELS_VERBOSE_FULL[message_data['comp_level']]

    elif message_type == 'alliance_selection':
        event_data = message_data['event']
        event_name = message_data['event_name']
        message += f"Alliances selected for {event_data['start_date']}-{event_data['end_date']}\n"
        if 'alliances' in event_data:
            count = 1
            for alliance in event_data['alliances']:
                message += str(count) + ": "
                message += ', '.join(unfrc(x) for x in alliance['picks'])
                message += "\n"
                count += 1
        else:
            message += "That's all I know, no details yet\n"
        message += "at " + event_name

    elif message_type == 'match_video':
        event_name = message_data['event_name']
        match_key = message_data['match']['key']
        message += f"A match video for {match_key} of {event_name} has been uploaded to "
        if "videos" in message_data['match']:
            for video in message_data['match']['videos']:
                if video['type'] == "youtube":
                    video_url = 'https://youtube.com/watch?v=' + video['key']
                    message += f'<{video_url}|Youtube> '

    elif message_type == 'awards_posted':
        awards = message_data['awards']
        event_name = message_data['event_name']
        message += "Awards Posted\n"
        for award_data in awards:
            message += f"{award_data['year']} {award_data['name']}: "
            for recepient in award_data['recipient_list']:
                if recepient['team_key']:
                    message += unfrc(recepient['team_key']) + " "
                if recepient['awardee']:
                    message += recepient['awardee']
                message += "\n"

    elif message_type == 'verification':
        print("Verification code: ", message_data)
        message = "Verification code: " + message_data

    elif message_type == 'ping':
        message += "Ping: " + message_data['desc']

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
        ch = hashlib.sha1()
        ch.update(tba_secret.encode('UTF-8'))
        ch.update(strdata)
        checksum = ch.hexdigest()
        if checksum != request.headers.get('X-TBA-Checksum'):
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

    #slack_token = os.environ['SLACK_PROD_TOKEN']
    url = "https://hooks.slack.com" + os.environ['SLACK_PROD']
    webhook = WebhookClient(url)
    r = webhook.send(text=message)
    return (r.body, r.status_code)


if __name__ == '__main__':
    class My_req:
        args = {
            "payload": """{
                "message_type": "ping",
                "message_data": {"desc": "Command line test"}
            }"""
        }
    test_req = My_req()
    print(tba_to_slack(test_req))
