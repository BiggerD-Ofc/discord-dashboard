import os
import requests
from flask import Flask, render_template, redirect, session, request, jsonify

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")

CLIENT_ID = "1256909611341189193"
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"
GUILDS_URL = "https://discord.com/api/users/@me/guilds"

OAUTH = (
    "https://discord.com/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    "&response_type=code"
    f"&redirect_uri={REDIRECT_URI}"
    "&scope=identify%20guilds"
)


@app.route("/")
def home():
    return redirect("/dashboard")


@app.route("/login")
def login():
    return redirect(OAUTH)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    session.clear()

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
        return f"OAuth error: {token}", 500

    auth = {"Authorization": f"Bearer {token['access_token']}"}

    user = requests.get(USER_URL, headers=auth).json()
    guilds = requests.get(GUILDS_URL, headers=auth).json()

    if not isinstance(guilds, list):
        guilds = []

    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{user.get('id')}/{user.get('avatar')}.png"
        if user.get("avatar")
        else "https://cdn.discordapp.com/embed/avatars/0.png"
    )

    session["user"] = {
        "id": user.get("id"),
        "username": user.get("username", "Unknown"),
        "avatar": avatar_url
    }

    session["guilds"] = guilds

    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    guilds = session.get("guilds", [])

    # SAFE CALC
    total_servers = len(guilds) if isinstance(guilds, list) else 0
    total_users = 0

    for g in guilds:
        try:
            total_users += g.get("approximate_member_count", 0)
        except:
            pass

    return render_template(
        "dashboard.html",
        user=session.get("user", {}),
        total_servers=total_servers,
        total_users=total_users,
        user_guilds=[]
    )


@app.route("/api/stats")
def stats():
    guilds = session.get("guilds", [])

    return jsonify({
        "total_servers": len(guilds) if isinstance(guilds, list) else 0,
        "total_users": 0
    })


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
