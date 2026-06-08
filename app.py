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

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    token = requests.post(TOKEN_URL, data=data, headers=headers).json()
    access_token = token.get("access_token")

    if not access_token:
        return f"TOKEN ERROR: {token}", 500

    auth = {"Authorization": f"Bearer {access_token}"}

    user = requests.get(USER_URL, headers=auth).json()
    guilds = requests.get(GUILDS_URL, headers=auth).json()

    if not isinstance(guilds, list):
        guilds = []

    # 💥 FIX AVATAR
    uid = user.get("id")
    avatar = user.get("avatar")

    if avatar:
        avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png"
    else:
        avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"

    # 💥 FIX USER SESSION (KLÍČOVÁ CHYBA BYLA TADY)
    session["user"] = {
        "id": uid,
        "username": user.get("username", "Unknown"),
        "avatar": avatar_url
    }

    # 💥 FIX GUILDS + STATS
    servers = []

    total_users = 0

    for g in guilds:
        servers.append({
            "id": g.get("id"),
            "name": g.get("name"),
            "icon": g.get("icon"),
            "members": g.get("approximate_member_count", 0)
        })

        try:
            total_users += int(g.get("approximate_member_count") or 0)
        except:
            pass

    session["guilds"] = servers

    session["stats"] = {
        "total_servers": len(servers),
        "total_users": total_users
    }

    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    stats = session.get("stats", {})

    return render_template(
        "dashboard.html",
        user=session["user"],
        user_guilds=session.get("guilds", []),
        total_servers=stats.get("total_servers", 0),
        total_users=stats.get("total_users", 0)
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


if __name__ == "__main__":
    app.run(debug=True)
