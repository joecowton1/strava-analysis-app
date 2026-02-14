import argparse
import requests

from src.config import get_settings

STRAVA_API = "https://www.strava.com/api/v3"

def create_sub():
    s = get_settings()
    if not s.callback_url:
        raise SystemExit(
            "STRAVA_CALLBACK_URL is empty. Set it to your public ngrok https URL + /strava/webhook"
        )

    print(f"Creating webhook subscription...")
    print(f"  Callback URL: {s.callback_url}")
    print(f"  Client ID: {s.client_id}")
    print(f"  Verify Token: {s.verify_token}")
    print()

    r = requests.post(
        f"{STRAVA_API}/push_subscriptions",
        data={
            "client_id": s.client_id,
            "client_secret": s.client_secret,
            "callback_url": s.callback_url,
            "verify_token": s.verify_token,
        },
        timeout=30,
    )
    
    if not r.ok:
        print(f"❌ Error {r.status_code}: {r.reason}")
        try:
            error_data = r.json()
            print(f"Details: {error_data}")
        except:
            print(f"Response: {r.text}")
        r.raise_for_status()
    
    print("✅ Webhook subscription created:")
    print(r.json())

def list_sub():
    s = get_settings()
    r = requests.get(
        f"{STRAVA_API}/push_subscriptions",
        params={
            "client_id": s.client_id,
            "client_secret": s.client_secret,
        },
        timeout=30,
    )
    r.raise_for_status()
    print(r.json())

def delete_sub(sub_id: int):
    s = get_settings()
    r = requests.delete(
        f"{STRAVA_API}/push_subscriptions/{sub_id}",
        params={
            "client_id": s.client_id,
            "client_secret": s.client_secret,
        },
        timeout=30,
    )
    r.raise_for_status()
    print({"deleted": sub_id})

def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("create")
    sp.add_parser("list")
    d = sp.add_parser("delete")
    d.add_argument("sub_id", type=int)
    args = ap.parse_args()

    if args.cmd == "create":
        create_sub()
    elif args.cmd == "list":
        list_sub()
    else:
        delete_sub(args.sub_id)

if __name__ == "__main__":
    main()