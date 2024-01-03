import os
import sys
import json
import time
import hashlib
from slack_sdk.webhook import WebhookClient
from slack_sdk.errors import SlackApiError

TBA_TEST_EVENT = "2014necmp"

#slack_token = os.environ['SLACK_PROD_TOKEN']
prod_url = "https://hooks.slack.com" + os.environ.get('SLACK_PROD')
test_url = "https://hooks.slack.com" + os.environ.get('SLACK_TEST')

os.environ['TZ'] = os.environ.get('TARGET_TZ', 'GMT')
time.tzset()

class TBA_parser:
    our_team = "0"
    message = ""
    env = "PROD"
    COMP_LEVELS_VERBOSE_FULL = {
        "qm": "Qualification",
        "ef": "Octo-finals",
        "qf": "Quarterfinals",
        "sf": "Semifinals",
        "f":  "Finals"
    }

    def __init__(self, payload):
        self.message_data = payload.get('message_data')
        self.message_type = payload.get('message_type')
        self.message = ""
        self.our_team = os.environ.get('FRC_TEAM', "0")

    def unfrc(self, team):
        # TBA uses 'frcNNNN' format for the team names, we drop 'frc'
        team = team.replace('frc','',1)
        if team == self.our_team:
            # if this is our team we make it bold (Markup)
            team = '*' + team + '*'
        return team

    def parse_tba(self):
        if self.message_data.get("event_key") == TBA_TEST_EVENT:
            self.env = "TEST"

        if self.message_type == 'upcoming_match':
            self.message += "Upcoming match"
            if 'predicted_time' in self.message_data:
                predicted = time.strftime("%H:%M",time.localtime(self.message_data['predicted_time']))
                self.message += " at " + predicted
            if 'scheduled_time' in self.message_data:
                scheduled = time.strftime("%H:%M",time.localtime(self.message_data['scheduled_time']))
                self.message += "\nOriginally scheduled " + scheduled
            if 'team_keys' in self.message_data:
                self.message += "\n[ "
                count = 0
                for team in self.message_data['team_keys']:
                    self.message += self.unfrc(team) +" "
                    count += 1
                    if count == 3:
                        self.message += "] vs. [ "
            self.message += "]\nMatch " + self.message_data.get('match_key')
            self.message += ' at ' + self.message_data.get("event_name")
            if 'webcast' in self.message_data:
                webcast = self.message_data['webcast']
                webcast_type = webcast.get('type')
                webcast_channel = webcast.get('channel')
                if webcast_type == "twitch":
                    video_url = f"https://www.twitch.tv/{webcast_channel}"
                    self.message += f'<{video_url}|Cast at Twitch> '
                elif webcast_type == "youtube":
                    video_url = f"https://youtube.com/watch?v={webcast_channel}"
                    self.message += f'<{video_url}|Cast at Youtube> '

        elif self.message_type == 'match_score':
            self.message += f"Match {str(self.message_data['match']['match_number'])} results:\n"
            for alliance in ['blue','red']:
                alliance_data = self.message_data['match']['alliances'][alliance]
                self.message += f"{alliance} [ "
                for team in alliance_data['team_keys']:
                    self.message += self.unfrc(team) +" "
                self.message += f"] scored {str(alliance_data['score'])}"
                self.message += "\n"

        elif self.message_type == 'schedule_updated':
            self.message += "A match added "
            if 'first_match_time' in self.message_data:
                first_match_time = time.strftime("%H:%M",time.localtime(self.message_data['first_match_time']))
                self.message += first_match_time
            self.message += "\nto " + self.message_data["event_name"]

        elif self.message_type == 'starting_comp_level':
            self.message += "Competition started. Level: " 
            self.message += self.COMP_LEVELS_VERBOSE_FULL.get(self.message_data.get('comp_level'))

        elif self.message_type == 'alliance_selection':
            event_data = self.message_data.get('event')
            event_name = self.message_data.get('event_name')
            self.message += f"Alliances selected for {event_name} ({event_data.get('end_date')})\n"
            if 'alliances' in event_data:
                count = 1
                for alliance in event_data['alliances']:
                    self.message += str(count) + ": "
                    self.message += ', '.join(self.unfrc(x) for x in alliance['picks'])
                    self.message += "\n"
                    count += 1
            else:
                print(f"No alliances? {event_data}")
                self.message += "That's all I know, no details yet\n"

        elif self.message_type == 'match_video':
            # Match Video is weird, it has the event key inside 'match' object
            if self.message_data.get('match').get('event_key') == TBA_TEST_EVENT:
                self.env = "TEST"
            event_name = self.message_data['event_name']
            match_key = self.message_data['match']['key']
            self.message += f"A match video for {match_key} of {event_name} has been uploaded\n"
            if "videos" in self.message_data['match']:
                for video in self.message_data['match']['videos']:
                    if video.get('type') == "youtube":
                        video_url = 'https://youtube.com/watch?v=' + video.get('key')
                        self.message += f'<{video_url}|Youtube> '

        elif self.message_type == 'awards_posted':
            awards = self.message_data.get('awards')
            event_name = self.message_data.get('event_name')
            self.message += "Awards Posted\n"
            for award_data in awards:
                self.message += f"{award_data['year']} {award_data['name']}: "
                for recepient in award_data['recipient_list']:
                    if recepient['team_key']:
                        self.message += self.unfrc(recepient['team_key']) + " "
                    if recepient['awardee']:
                        self.message += recepient['awardee']
                    self.message += "\n"

        elif self.message_type == 'broadcast':
            self.message += f"Broadcast: {self.message_data.get('title')}\n"
            self.message += self.message_data.get('desc')
            url = self.message_data.get('url')
            if url:
                self.message += f"\nClick: {url}"

        elif self.message_type == 'verification':
            self.env = "TEST"
            print("Verification code: ", self.message_data)
            self.message = "Verification code: " + self.message_data.get("verification_key")

        elif self.message_type == 'ping':
            self.env = "TEST"
            self.message += "Ping: " + self.message_data.get('desc', 'Null')

        else:
            self.env = "TEST"
            self.message += "Unprogrammed notification at "
            self.message += time.asctime(time.localtime(time.time())) + "\n"
            self.message += self.message_type

        return self.message

def tba_to_slack(request):
    strdata = None
    payload = None

    print(f"Request type: {request.content_type}")
    if request.content_type.find("application/json") >= 0:
        # The body must be a JSON
        strdata = request.data
        payload = request.get_json()

    elif request.args and 'payload' in request.args:
        # So we can use a HTML form for debugging
        strdata = request.args.get('payload')
        payload = json.loads(strdata)

    else:
        print("Malformed request, payload not found")
        return (f'Bad request', 400)

    tba_secret = os.environ.get('TBA_SECRET')
    if tba_secret:
        # The TBA Secret is set in the environment, let's check it
        ch = hashlib.sha1()
        ch.update(tba_secret.encode('UTF-8'))
        ch.update(strdata)
        checksum = ch.hexdigest()
        if checksum != request.headers.get('X-TBA-Checksum'):
            # The same checksum must be computed at TBA and sent in a header and match
            print(f"Checksum error happened. Checksum should be: {checksum}")
            return ("checksum error", 403)

    if payload and 'message_type' in payload:
        message_type = payload['message_type']
        print(f"Processing {message_type}")
    else:
        # Otherwise no idea what to do
        print("No message type in the payload")
        return (f'Empty request. Nothing happened', 400)

    parser = TBA_parser(payload)
    try:
        message = parser.parse_tba()
    except Exception as e:
        print(f"Exception [{e}]\ninput data: {strdata}")
        message = f"Couldn't parse '{message_type}' notification. Please check TBA."

    # Parsing the input data the parser can see if it's a TEST data
    if parser.env == "PROD":
        url = prod_url
    else:
        url = test_url

    webhook = WebhookClient(url)
    r = webhook.send(text=message)
    return (r.body, r.status_code)


if __name__ == '__main__':
    str = " ".join(sys.argv[1:])
    payload = {
        "message_type": "ping",
        "message_data": {"desc": f"CLI test: {str}"}
    }
    class My_req:
        args = {"payload": json.dumps(payload)}
        content_type = "text/plain"

    test_req = My_req()
    print(tba_to_slack(test_req))
