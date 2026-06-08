import os
import requests
from flask import Flask, redirect, url_for, session, request, render_template, jsonify

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

DISCORD_API = "https://discord.com/api"


# -------------------------
# HELPERS
# -------------------------
def discord_api(endpoint, token):
    return requests.get(
        f"{DISCORD_API}{endpoint}",
        headers={"Authorization": f"Bearer {token}"}
    ).json()


def is_logged():
    return "access_token" in session


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

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

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

    # GUILDS (CUT DOWN = FIX COOKIE SIZE)
    guilds_raw = discord_api("/users/@me/guilds", access_token)

    guilds = []
    for g in guilds_raw:
        guilds.append({
            "id": g["id"],
            "name": g["name"],
            "icon": g.get("icon"),
            "permissions": g.get("permissions", "0")
        })

    session["user"] = {
        "id": user["id"],
        "username": user["username"],
        "avatar": (
            f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"
            if user.get("avatar") else None
        )
    }

    session["guilds"] = guilds

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

    user = session.get("user")
    guilds = session.get("guilds", [])

    # ADMIN FILTER (0x8 = ADMIN)
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
# SERVERS PAGE (FIX FOR BUILDERROR)
# -------------------------
@app.route("/servers")
def servers():
    if not is_logged():
        return redirect(url_for("login"))

    return render_template(
        "servers.html",
        user=session.get("user"),
        guilds=session.get("guilds", [])
    )


# -------------------------
# STATS API (SAFE)
# -------------------------
@app.route("/api/stats")
def stats():
    if not is_logged():
        return jsonify({"error": "not logged"}), 401

    guilds = session.get("guilds", [])

    return jsonify({
        "total_servers": len(guilds),
        "total_users": 0
    })


# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
