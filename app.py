import os
import requests
from flask import Flask, redirect, url_for, session, request, render_template, jsonify

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

# ENV (SAFE)
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

DISCORD_API = "https://discord.com/api"


# -------------------------
# SAFETY CHECK (PREVENT None CRASH)
# -------------------------
if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    print("❌ Missing ENV variables (DISCORD_CLIENT_ID / SECRET / REDIRECT_URI)")


# -------------------------
# HELPERS
# -------------------------
def discord_api(endpoint, token):
    r = requests.get(
        f"{DISCORD_API}{endpoint}",
        headers={"Authorization": f"Bearer {token}"}
    )
    return r.json()


def is_logged():
    return session.get("access_token") is not None


def get_guilds(token):
    return discord_api("/users/@me/guilds", token)


# -------------------------
# HOME
# -------------------------
@app.route("/")
def home():
    return redirect(url_for("dashboard"))


# -------------------------
# LOGIN
# -------------------------
@app.route("/login")
def login():
    if not CLIENT_ID or not REDIRECT_URI:
        return "OAuth config error (ENV missing)", 500

    return redirect(
        "https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=identify%20email%20guilds"
    )


# -------------------------
# CALLBACK
# -------------------------
@app.route("/callback")
def callback():
    code = request.args.get("code")

    if not code:
        return "No code provided", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify email guilds"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    r = requests.post(
        f"{DISCORD_API}/oauth2/token",
        data=data,
        headers=headers
    )

    if r.status_code != 200:
        return f"OAuth failed: {r.text}", 400

    token_data = r.json()
    access_token = token_data["access_token"]

    session["access_token"] = access_token

    # USER INFO
    user = discord_api("/users/@me", access_token)

    # ⚠️ IMPORTANT FIX:
    # DO NOT STORE GUILDS IN SESSION (COOKIE LIMIT FIX)
    guilds_raw = get_guilds(access_token)

    # FILTER + CLEAN ONLY (NO SESSION STORAGE)
    guilds = [
        {
            "id": g["id"],
            "name": g["name"],
            "icon": g.get("icon"),
            "permissions": g.get("permissions", "0")
        }
        for g in guilds_raw
    ]

    session["user"] = {
        "id": user["id"],
        "username": user["username"],
        "avatar": (
            f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"
            if user.get("avatar") else None
        )
    }

    return redirect(url_for("dashboard"))


# -------------------------
# LOGOUT
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------------
# DASHBOARD
# -------------------------
@app.route("/dashboard")
def dashboard():
    if not is_logged():
        return redirect(url_for("login"))

    access_token = session.get("access_token")
    user = session.get("user")

    # LIVE GUILDS (NO SESSION)
    guilds = get_guilds(access_token)

    # ADMIN FILTER
    user_guilds = [
        g for g in guilds
        if int(g.get("permissions", 0)) & 0x8
    ]

    bot_servers = guilds

    return render_template(
        "dashboard.html",
        user=user,
        user_guilds=user_guilds,
        bot_servers=bot_servers,
        total_servers=len(guilds),
        total_users=0
    )


# -------------------------
# SERVERS PAGE
# -------------------------
@app.route("/servers")
def servers():
    if not is_logged():
        return redirect(url_for("login"))

    token = session.get("access_token")

    guilds = discord_api("/users/@me/guilds", token)

    # ONLY ADMIN / MANAGE SERVER
    manageable = [
        g for g in guilds
        if (int(g.get("permissions", 0)) & 0x8) or (int(g.get("permissions", 0)) & 0x20)
    ]

    return render_template(
        "servers.html",
        user=session.get("user"),
        servers=manageable
    )
# -------------------------
# STATS API
# -------------------------
@app.route("/api/stats")
def stats():
    if not is_logged():
        return jsonify({"error": "not logged"}), 401

    guilds = get_guilds(session.get("access_token"))

    return jsonify({
        "total_servers": len(guilds),
        "total_users": 0
    })


# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
