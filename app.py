import os
import requests
from flask import Flask, render_template, redirect, url_for, session, request, jsonify

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

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")


# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/dashboard")


# ---------------- LOGIN ----------------
@app.route("/login")
def login():
    return redirect(OAUTH)


# ---------------- CALLBACK ----------------
@app.route("/callback")
def callback():
    code = request.args.get("code")

    if not CLIENT_SECRET:
        return "❌ Missing DISCORD_CLIENT_SECRET", 500

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

    # ---------------- AVATAR FIX ----------------
    uid = user.get("id")
    avatar = user.get("avatar")

    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png"
        if avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    )

    # ---------------- USER SESSION ----------------
    session["user"] = {
        "id": uid,
        "username": user.get("username", "Unknown"),
        "avatar": avatar_url
    }

    # ---------------- FILTER ADMIN / OWNER ----------------
    admin_servers = []
    total_users = 0

    for g in guilds:
        perms = int(g.get("permissions", 0))

        is_owner = g.get("owner", False)
        is_admin = (perms & 0x8) == 0x8

        members = g.get("approximate_member_count", 0)

        server = {
            "id": g.get("id"),
            "name": g.get("name"),
            "icon": g.get("icon"),
            "members": members,
            "owner": is_owner,
            "admin": is_admin
        }

        total_users += int(members or 0)

        if is_owner or is_admin:
            admin_servers.append(server)

    # ---------------- SESSION STORE ----------------
    session["guilds"] = guilds
    session["admin_guilds"] = admin_servers
    session["stats"] = {
        "total_servers": len(guilds),
        "total_users": total_users
    }

    return redirect("/dashboard")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    stats = session.get("stats", {})

    return render_template(
        "dashboard.html",
        user=session["user"],
        user_guilds=session.get("admin_guilds", []),
        total_servers=stats.get("total_servers", 0),
        total_users=stats.get("total_users", 0)
    )


# ---------------- API ----------------
@app.route("/api/stats")
def stats():
    return jsonify(session.get("stats", {"total_servers": 0, "total_users": 0}))


@app.route("/api/servers")
def servers():
    return jsonify(session.get("guilds", []))


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
