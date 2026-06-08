import os
import requests
from flask import Flask, render_template, redirect, url_for, session, request, jsonify

CLIENT_ID = "1256909611341189193"
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

OAUTH = (
    "https://discord.com/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    "&response_type=code"
    f"&redirect_uri={REDIRECT_URI}"
    "&scope=identify%20guilds"
)

TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"
GUILDS_URL = "https://discord.com/api/users/@me/guilds"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")


@app.route("/")
def home():
    return redirect("/dashboard")


@app.route("/login")
def login():
    return redirect(OAUTH)


@app.route("/callback")
def callback():
    code = request.args.get("code")

    if not CLIENT_SECRET:
        return "❌ Missing DISCORD_CLIENT_SECRET in Render env", 500

    if not REDIRECT_URI:
        return "❌ Missing DISCORD_REDIRECT_URI in Render env", 500

    try:
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        token = requests.post(TOKEN_URL, data=data, headers=headers).json()

        if "access_token" not in token:
            return f"❌ TOKEN ERROR: {token}", 500

        auth = {"Authorization": f"Bearer {token['access_token']}"}

        user = requests.get(USER_URL, headers=auth).json()
        guilds = requests.get(GUILDS_URL, headers=auth).json()

        if not isinstance(guilds, list):
            guilds = []

        avatar = user.get("avatar")
        uid = user.get("id")

        session["user"] = {
            "id": uid,
            "username": user.get("username"),
            "avatar": (
                f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png"
                if avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
            )
        }

        session["guilds"] = guilds
        session["stats"] = {
            "total_servers": len(guilds),
            "total_users": 0
        }

        return redirect("/dashboard")

    except Exception as e:
        return f"❌ CALLBACK CRASH: {str(e)}", 500


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    return render_template(
        "dashboard.html",
        user=session["user"],
        user_guilds=session.get("guilds", []),
        total_servers=session.get("stats", {}).get("total_servers", 0),
        total_users=session.get("stats", {}).get("total_users", 0)
    )


@app.route("/api/stats")
def stats():
    return jsonify(session.get("stats", {"total_servers": 0, "total_users": 0}))


@app.route("/api/servers")
def servers():
    return jsonify(session.get("guilds", []))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
