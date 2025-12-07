import os
import sys
import json
import time
import hashlib
import hmac

from slack_sdk.webhook import WebhookClient
from typing import Optional, Any, Union
from werkzeug.wrappers import Request

TBA_TEST_EVENT: str = "2014necmp"

# Let the parser decide whether this is a test run based on the content
# and then the sender will choose between these two URLs
prod_url: str = "https://hooks.slack.com" + os.environ.get("SLACK_PROD", "")
test_url: str = "https://hooks.slack.com" + os.environ.get("SLACK_TEST", "")


def slack_time(t: Optional[Union[int, float]] = None) -> str:
    if t is None:
        t = time.time()
    return f"""<!date^{int(t)}^{{time}}|{time.strftime("%H:%M GMT", time.gmtime(t))}>"""


class TBA_parser:
    our_team: str = "0"
    message: str = ""
    env: str = "PROD"
    COMP_LEVELS_VERBOSE_FULL: dict[str,str] = {
        "qm": "Qualification",
        "ef": "Octo-finals",
        "qf": "Quarterfinals",
        "sf": "Semifinals",
        "f":  "Finals"
    }
    message_data: dict[str, Any] = {}
    message_type: str = ""

    def __init__(self) -> None:
        self.message: str = ""
        self.our_team: str = os.environ.get("FRC_TEAM", "0")

    def unfrc(self, team: str) -> str:
        # TBA uses "frcNNNN" format for the team names, we drop "frc"
        team = team.replace("frc","",1)
        if team == self.our_team:
            # if this is our team we make it bold (Markup)
            team = "*" + team + "*"
        return team

    def parse_tba(self, payload: dict[str, Any]) -> str:
        self.message_data = payload.get("message_data", {})
        self.message_type = payload.get("message_type", "unknown")

        if self.message_data.get("event_key") == TBA_TEST_EVENT:
            self.env = "TEST"

        if self.message_type == "upcoming_match":
            self.message += "Upcoming match " + self.message_data.get("match_key", "unknown") + "\n"
            if "scheduled_time" in self.message_data:
                scheduled: str = slack_time(self.message_data["scheduled_time"])
                self.message += "Schedule time: " + scheduled
            if "predicted_time" in self.message_data:
                predicted: str = slack_time(self.message_data["predicted_time"])
                self.message += " Estimated: " + predicted
            if "team_keys" in self.message_data:
                self.message += "\n[ "
                count: int = 0
                for team in self.message_data["team_keys"]:
                    self.message += self.unfrc(team) + " "
                    count += 1
                    if count == 3:
                        self.message += "] vs. [ "
            self.message += "]\nat " + self.message_data.get("event_name", "unknown event")
            if "webcast" in self.message_data:
                webcast: dict[str, str] = self.message_data["webcast"]
                webcast_type: str = webcast.get("type", "")
                webcast_channel: str = webcast.get("channel", "")
                if webcast_type == "twitch":
                    video_url = f"https://www.twitch.tv/{webcast_channel}"
                    self.message += f" | <{video_url}|Cast at Twitch> "
                elif webcast_type == "youtube":
                    video_url = f"https://youtube.com/watch?v={webcast_channel}"
                    self.message += f" | <{video_url}|Cast at Youtube> "

        elif self.message_type == "match_score":
            match_data: dict[str, Any] = self.message_data.get("match", {})
            if match_data and "alliances" in match_data:
                self.message += f"""Match {str(match_data.get("match_number", ""))} results:\n"""
                for alliance in match_data["alliances"].keys():
                    alliance_data: dict[str, Any] = match_data["alliances"][alliance]
                    self.message += f"{alliance} [ "
                    for team in alliance_data["team_keys"]:
                        self.message += self.unfrc(team) +" "
                    self.message += f"""] scored {str(alliance_data["score"])}"""
                    self.message += "\n"

        elif self.message_type == "schedule_updated":
            self.message += "A match added "
            if "first_match_time" in self.message_data:
                first_match_time = slack_time(self.message_data["first_match_time"])
                self.message += first_match_time
            self.message += "\nto " + self.message_data["event_name"]

        elif self.message_type == "starting_comp_level":
            self.message += "Competition started. Level: " 
            self.message += self.COMP_LEVELS_VERBOSE_FULL.get(self.message_data.get("comp_level",""), "Unknown")

        elif self.message_type == "alliance_selection":
            event_data: dict[str, Any] = self.message_data.get("event", {})
            event_name: str = self.message_data.get("event_name", "unknown event")
            self.message += f"""Alliances selected for {event_name} ({event_data.get("end_date", "no date")})\n"""
            # Older TBA notifications had alliances list in event data, not anymore
            if "alliances" in event_data:
                count = 1
                for alliance in event_data["alliances"]:
                    self.message += str(count) + ": "
                    self.message += ", ".join(self.unfrc(x) for x in alliance["picks"])
                    self.message += "\n"
                    count += 1

        elif self.message_type == "match_video":
            match_data = self.message_data.get("match", {})
            # Match Video is weird, it has the event key inside "match" object
            if match_data.get("event_key", TBA_TEST_EVENT) == TBA_TEST_EVENT:
                self.env = "TEST"
            event_name = self.message_data.get("event_name", "unknown event")
            match_key: str = match_data.get("key", "unknown match")
            self.message += f"A match video for {match_key} of {event_name} has been uploaded\n"
            if "videos" in match_data:
                for video in match_data["videos"]:
                    if video.get("type") == "youtube":
                        video_url = "https://youtube.com/watch?v=" + video.get("key")
                        self.message += f"<{video_url}|Youtube> "

        elif self.message_type == "awards_posted":
            awards: list[dict[str, Any]] = self.message_data.get("awards", [])
            event_name = self.message_data.get("event_name", "unknown event")
            self.message += "Awards Posted\n"
            for award_data in awards:
                self.message += f"""{award_data["year"]} {award_data["name"]}: """
                for recepient in award_data["recipient_list"]:
                    if recepient["team_key"]:
                        self.message += self.unfrc(recepient["team_key"]) + " "
                    if recepient["awardee"]:
                        self.message += recepient["awardee"]
                    self.message += "\n"

        elif self.message_type == "broadcast":
            self.message += f"""Broadcast: {self.message_data.get("title")}\n"""
            self.message += self.message_data.get("desc", "No description")
            url = self.message_data.get("url")
            if url:
                self.message += f"\nClick: {url}"

        elif self.message_type == "verification":
            self.env = "TEST"
            print("Verification code: ", self.message_data)
            self.message = "Verification code: " + self.message_data.get("verification_key", "Null")

        elif self.message_type == "ping":
            self.env = "TEST"
            self.message += "Ping: " + self.message_data.get("desc", "Null")

        else:
            self.env = "TEST"
            self.message += "Unprogrammed notification at "
            self.message += slack_time() + "\n"
            self.message += self.message_type

        return self.message


def tba_to_slack(request: Request) -> tuple[str, int]:
    message: str = ""
    message_type: str = ""

    tba_secret: str = os.environ.get("TBA_SECRET", "")
    if tba_secret:
        # The TBA Secret is set in the environment, let's check it
        checksum: hmac.HMAC = hmac.new(
                tba_secret.encode("utf-8"),
                request.data,
                hashlib.sha256
            )
        if checksum.hexdigest() != request.headers.get("X-TBA-HMAC"):
            # The same checksum must be computed at TBA and sent in a header and match
            print(f"HMAC error happened. Checksum should be: {checksum.hexdigest()}")
            return ("Message Authentication failed", 401)
    # Otherwise, if the secret is not set, we skip the check - it could be a local test
    # Don't forget to set the TBA_SECRET in production!

    # Property json of the Request gives us the parsed JSON payload
    # or throws an exception (HTTP 415 Unsupported Media Type) for us
    payload: dict[str, Any] = request.json
    if payload and "message_type" in payload:
        message_type = payload["message_type"]
        print(f"Processing {message_type}")
    else:
        # Otherwise no idea what to do
        print("No message type in the payload")
        return ("Malformed request. Nothing happened", 422)

    parser = TBA_parser()
    try:
        message = parser.parse_tba(payload)
    except Exception as e:
        print(f"Exception [{e}]\ninput data: {request.data!r}")
        message = f"Couldn't parse '{message_type}' notification. Please check TBA."

    # Parsing the input data the parser can see if it's a TEST data
    if parser.env == "PROD":
        url = prod_url
    else:
        url = test_url

    webhook = WebhookClient(url)
    r = webhook.send(text=message)
    return (r.body, r.status_code)


if __name__ == "__main__":
    arg_str: str = " ".join(sys.argv[1:])
    if not arg_str:
        arg_str = "Now is " + slack_time()
    payload = {
        "message_type": "ping",
        "message_data": {"desc": f"CLI test: {arg_str}"}
    }
    data = json.dumps(payload).encode("UTF-8")
    test_req = Request.from_values(
        data=data,
        content_type="application/json",
        headers={
            "X-TBA-HMAC": hmac.new(
                os.environ.get("TBA_SECRET", "").encode("UTF-8"),
                data,
                hashlib.sha256
            ).hexdigest()
        }
    )
    print(tba_to_slack(test_req))
