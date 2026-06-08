import os
import logging
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for, session, request
import requests

logging.basicConfig(level=logging.INFO)

CLIENT_ID = "1256909611341189193"
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = "https://dash.quanty-bot.linkpc.net/callback"

OAUTH_URL = (
    "https://discord.com/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    "&response_type=code"
    f"&redirect_uri={REDIRECT_URI}"
    "&scope=identify%20email%20guilds"
)

TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"
GUILDS_URL = "https://discord.com/api/users/@me/guilds"


def create_app():
    app = Flask(__name__, static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

    app.config["BOT_STATS"] = {
        "total_servers": 0,
        "total_users": 0
    }

    # ---------------- HOME ----------------
    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    # ---------------- LOGIN ----------------
    @app.route("/login")
    def login():
        return redirect(OAUTH_URL)

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

        if not isinstance(guilds, list):
            guilds = []

        user_id = user.get("id")
        avatar = user.get("avatar")

        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png"
            if avatar else
            "https://cdn.discordapp.com/embed/avatars/0.png"
        )

        session["user"] = {
            "id": user_id,
            "username": user.get("username", "Unknown"),
            "discriminator": user.get("discriminator", ""),
            "avatar": avatar_url
        }

        # admin guilds
        admin = []
        for g in guilds:
            try:
                if int(g.get("permissions", 0)) & 0x8:
                    admin.append(g)
            except:
                pass

        session["user_guilds"] = admin
        session["bot_servers"] = admin

        # stats (demo)
        app.config["BOT_STATS"]["total_servers"] = len(guilds)
        app.config["BOT_STATS"]["total_users"] = max(len(guilds) * 20, 1)

        return redirect(url_for("dashboard"))

    # ---------------- DASHBOARD ----------------
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        stats = app.config["BOT_STATS"]

        return render_template(
            "dashboard.html",
            user=session.get("user", {}),
            user_guilds=session.get("user_guilds", []),
            bot_servers=session.get("bot_servers", []),
            total_servers=stats["total_servers"],
            total_users=stats["total_users"]
        )

    # ---------------- SERVERS PAGE ----------------
    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect(url_for("home"))

        return render_template(
            "servers.html",
            user=session.get("user", {}),
            user_guilds=session.get("user_guilds", [])
        )

    # ---------------- API SERVERS (FIX JS) ----------------
    @app.route("/api/servers")
    def api_servers():
        if "user" not in session:
            return {"error": "unauthorized"}, 401

        guilds = session.get("user_guilds", [])

        return [
            {
                "id": g.get("id"),
                "name": g.get("name"),
                "icon": g.get("icon")
            }
            for g in guilds
        ]

    # ---------------- API STATS ----------------
    @app.route("/api/stats")
    def stats():
        return app.config["BOT_STATS"]

    # ---------------- LOGOUT ----------------
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
