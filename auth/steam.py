import os
from urllib.parse import urljoin, urlparse, urlencode

import requests
from flask import current_app, url_for


STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"


def get_base_url():
    base_url = (
        current_app.config.get("PUBLIC_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    )

    return base_url.rstrip("/")


def get_steam_callback_url():
    return f"{get_base_url()}{url_for('auth.steam_callback')}"


def build_steam_login_url():
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": get_steam_callback_url(),
        "openid.realm": f"{get_base_url()}/",
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }

    return f"{STEAM_OPENID_URL}?{urlencode(params)}"


def safe_next_url(target=None):
    default_url = url_for("profile.index")

    if not target:
        return default_url

    base_url = get_base_url()
    absolute_target = urljoin(base_url, target)

    parsed_target = urlparse(absolute_target)
    parsed_base = urlparse(base_url)

    if (
        parsed_target.scheme in ("http", "https")
        and parsed_target.netloc == parsed_base.netloc
    ):
        return absolute_target

    return default_url


def parse_key_value_response(text):
    result = {}

    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()

    return result


def verify_openid_response(args):
    data = {}

    for key, value in args.items():
        if key.startswith("openid."):
            data[key] = value

    if data.get("openid.mode") != "id_res":
        return False

    data["openid.mode"] = "check_authentication"

    try:
        response = requests.post(
            STEAM_OPENID_URL,
            data=data,
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException:
        current_app.logger.exception("Steam OpenID verification request failed")
        return False

    parsed_response = parse_key_value_response(response.text)

    return parsed_response.get("is_valid") == "true"


def extract_steam_id(args):
    claimed_id = args.get("openid.claimed_id") or args.get("openid.identity") or ""

    steam_id = claimed_id.rsplit("/", 1)[-1]

    if steam_id.isdigit():
        return steam_id

    return None


def fetch_steam_user(steam_id):
    api_key = current_app.config.get("STEAM_API_KEY")

    user = {
        "steam_id": steam_id,
        "nickname": f"Player{steam_id[-4:]}",
        "avatar_url": "",
        "profile_url": f"https://steamcommunity.com/profiles/{steam_id}",
        "is_authenticated": True,
    }

    if not api_key:
        current_app.logger.warning(
            "STEAM_API_KEY is empty. Steam login works, but profile data will be limited."
        )
        return user

    try:
        response = requests.get(
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
            params={
                "key": api_key,
                "steamids": steam_id,
            },
            timeout=15,
        )
        response.raise_for_status()

        payload = response.json()
        players = payload.get("response", {}).get("players", [])

        if not players:
            return user

        player = players[0]

        user.update(
            {
                "nickname": player.get("personaname") or user["nickname"],
                "avatar_url": (
                    player.get("avatarfull")
                    or player.get("avatarmedium")
                    or player.get("avatar")
                    or ""
                ),
                "profile_url": player.get("profileurl") or user["profile_url"],
            }
        )

    except requests.RequestException:
        current_app.logger.exception("Failed to fetch Steam user profile")

    return user