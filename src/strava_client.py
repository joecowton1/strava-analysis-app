import time, requests

STRAVA_API = "https://www.strava.com/api/v3"
STRAVA_OAUTH = "https://www.strava.com/oauth/token"

class StravaClient:
    def __init__(self, client_id: int, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def refresh_access_token(self, refresh_token: str) -> dict:
        r = requests.post(STRAVA_OAUTH, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        })
        r.raise_for_status()
        return r.json()

    def _request(self, url: str, access_token: str, params=None):
        r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params)
        if r.status_code == 429:
            time.sleep(10)
            r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params)
        r.raise_for_status()
        return r.json()

    def get_activity(self, token: str, activity_id: int) -> dict:
        return self._request(f"{STRAVA_API}/activities/{activity_id}", token)

    def get_activity_streams(self, token: str, activity_id: int) -> dict:
        return self._request(
            f"{STRAVA_API}/activities/{activity_id}/streams",
            token,
            params={"keys": "time,watts,heartrate,cadence,velocity_smooth,altitude", "key_by_type": True},
        )
