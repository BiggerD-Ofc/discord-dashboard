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
    "&scope=identify%20email%20guilds%20guilds.members.read"
)

TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"
GUILDS_URL = "https://discord.com/api/users/@me/guilds"


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev")

    # ---------------- HOME ----------------
    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    # ---------------- LOGIN ----------------
    @app.route("/login")
    def login():
        return redirect(OAUTH)

    # ---------------- CALLBACK ----------------
    @app.route("/callback")
    def callback():
        code = request.args.get("code")
        if not code:
            return "Missing code", 400

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

        user = requests.get(USER_URL, headers=auth).json()
        guilds = requests.get(GUILDS_URL, headers=auth).json()

        # ---------------- SAFE GUARDS ----------------
        if not isinstance(guilds, list):
            guilds = []

        user_id = user.get("id")
        avatar = user.get("avatar")

        # ---------------- AVATAR FIX ----------------
        if avatar:
            ext = "gif" if avatar.startswith("a_") else "png"
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.{ext}"
        else:
            avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"

        session["user"] = {
            "id": user_id,
            "username": user.get("username", "Unknown"),
            "avatar": avatar_url
        }

        # ---------------- ADMIN SERVERS FIX ----------------
        admin_guilds = []

        for g in guilds:
            perms = int(g.get("permissions", 0))

            # 0x8 = ADMINISTRATOR
            if perms & 0x8:
                admin_guilds.append({
                    "id": g.get("id"),
                    "name": g.get("name"),
                    "icon": g.get("icon"),
                    "member_count": g.get("member_count", 0)
                })

        session["user_guilds"] = admin_guilds
        session["bot_servers"] = admin_guilds

        # ---------------- STATS (STABLE FAKE BUT CONSISTENT) ----------------
        session["stats"] = {
            "total_servers": len(guilds),
            "total_users": len(guilds) * 12
        }

        return redirect(url_for("dashboard"))

    # ---------------- DASHBOARD ----------------
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        stats = session.get("stats", {"total_servers": 0, "total_users": 0})

        return render_template(
            "dashboard.html",
            user=session["user"],
            user_guilds=session.get("user_guilds", []),
            bot_servers=session.get("bot_servers", []),
            total_servers=stats["total_servers"],
            total_users=stats["total_users"]
        )

    # ---------------- SERVERS ----------------
    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect(url_for("home"))

        return render_template(
            "servers.html",
            user=session["user"],
            user_guilds=session.get("user_guilds", [])
        )

    # ---------------- API ----------------
    @app.route("/api/stats")
    def stats():
        return session.get("stats", {"total_servers": 0, "total_users": 0})

    @app.route("/api/servers")
    def api_servers():
        return session.get("user_guilds", [])

    # ---------------- LOGOUT ----------------
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
