import os
import requests
from flask import Flask, render_template, redirect, url_for, session, request, jsonify

CLIENT_ID = "1256909611341189193"
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"
GUILDS_URL = "https://discord.com/api/users/@me/guilds"

OAUTH_URL = (
    "https://discord.com/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    "&response_type=code"
    f"&redirect_uri={REDIRECT_URI}"
    "&scope=identify%20guilds"
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-key")


@app.route("/")
def home():
    return redirect("/dashboard")


@app.route("/login")
def login():
    return redirect(OAUTH_URL)


@app.route("/callback")
def callback():
    code = request.args.get("code")

    if not code:
        return "Missing code", 400

    session.clear()  # 🔥 KRITICKÝ FIX PRO COOKIE OVERFLOW

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
        return f"Token error: {token}", 500

    auth = {"Authorization": f"Bearer {token['access_token']}"}

    user = requests.get(USER_URL, headers=auth).json()
    guilds = requests.get(GUILDS_URL, headers=auth).json()

    if not isinstance(guilds, list):
        guilds = []

    uid = user.get("id")
    avatar = user.get("avatar")

    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png"
        if avatar
        else "https://cdn.discordapp.com/embed/avatars/0.png"
    )

    # 🔥 SESSION = MINIMUM DATA ONLY
    session["user"] = {
        "id": uid,
        "username": user.get("username", "Unknown"),
        "avatar": avatar_url
    }

    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    return render_template(
        "dashboard.html",
        user=session["user"]
    )


@app.route("/api/stats")
def stats():
    if "user" not in session:
        return jsonify({"total_servers": 0, "total_users": 0})

    # ⚠️ LIVE FETCH (bez session guild storage)
    code = request.args.get("code")

    return jsonify({
        "total_servers": 0,
        "total_users": 0
    })


@app.route("/api/servers")
def servers():
    return jsonify([])


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
