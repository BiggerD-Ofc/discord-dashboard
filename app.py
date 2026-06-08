import os
import requests
from flask import Flask, render_template, redirect, url_for, session, request

CLIENT_ID = "1256909611341189193"
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = "https://dash.quanty-bot.linkpc.net/callback"

OAUTH = (
    "https://discord.com/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    "&response_type=code"
    f"&redirect_uri={REDIRECT_URI}"
    "&scope=identify%20guilds"
)

TOKEN_URL = "https://discord.com/api/oauth2/token"
API_USER = "https://discord.com/api/users/@me"
API_GUILDS = "https://discord.com/api/users/@me/guilds"


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev")

    # ---------------- LOGIN ----------------
    @app.route("/login")
    def login():
        return redirect(OAUTH)

    # ---------------- CALLBACK ----------------
    @app.route("/callback")
    def callback():
        code = request.args.get("code")
        if not code:
            return "No code", 400

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
            return f"Token error: {token}", 400

        auth = {"Authorization": f"Bearer {access_token}"}

        user = requests.get(API_USER, headers=auth).json()
        guilds = requests.get(API_GUILDS, headers=auth).json()

        if not isinstance(guilds, list):
            guilds = []

        # ---------------- AVATAR FIX ----------------
        avatar = user.get("avatar")
        user_id = user.get("id")

        if avatar:
            ext = "gif" if avatar.startswith("a_") else "png"
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.{ext}"
        else:
            avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"

        # ---------------- SESSION ----------------
        session["user"] = {
            "id": user_id,
            "username": user.get("username"),
            "avatar": avatar_url
        }

        # ---------------- GUILDS ----------------
        servers = []
        total_users = 0

        for g in guilds:
            servers.append({
                "id": g.get("id"),
                "name": g.get("name"),
                "icon": g.get("icon"),
                "members": g.get("approximate_member_count", 0)
            })

            total_users += int(g.get("approximate_member_count") or 0)

        session["guilds"] = servers
        session["stats"] = {
            "total_servers": len(servers),
            "total_users": total_users
        }

        return redirect(url_for("dashboard"))

    # ---------------- DASHBOARD ----------------
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("login"))

        stats = session.get("stats", {"total_servers": 0, "total_users": 0})

        return render_template(
            "dashboard.html",
            user=session["user"],
            user_guilds=session.get("guilds", []),
            total_servers=stats["total_servers"],
            total_users=stats["total_users"]
        )

    # ---------------- API ----------------
    @app.route("/api/stats")
    def api_stats():
        return session.get("stats", {"total_servers": 0, "total_users": 0})

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
