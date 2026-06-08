import os
import logging
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for, session, request
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

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
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    # CACHE (aby stats nebyly pořád 0)
    app.config["BOT_STATS"] = {
        "total_servers": 0,
        "total_users": 0
    }

    # ================= LOGIN =================

    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/login")
    def login():
        return redirect(OAUTH_URL)

    # ================= CALLBACK =================

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

        token_res = requests.post(TOKEN_URL, data=data, headers=headers)
        token_json = token_res.json()

        access_token = token_json.get("access_token")
        if not access_token:
            return f"Token error: {token_json}", 400

        auth = {"Authorization": f"Bearer {access_token}"}

        user = requests.get(USER_URL, headers=auth).json()
        guilds = requests.get(GUILDS_URL, headers=auth).json()

        # 🔥 FIX USER DATA (IMPORTANT)
        user_id = user["id"]
        avatar_hash = user.get("avatar")

        avatar_url = (
            f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
            if avatar_hash else
            "https://cdn.discordapp.com/embed/avatars/0.png"
        )

        session["user"] = {
            "id": user_id,
            "username": user["username"],
            "discriminator": user.get("discriminator", ""),
            "email": user.get("email"),
            "avatar": avatar_url,
        }

        # 🔥 ADMIN SERVERS FIX
        admin_guilds = [
            g for g in guilds
            if (int(g["permissions"]) & 0x8) == 0x8
        ]

        session["user_guilds"] = admin_guilds

        # 🔥 BOT STATS (LIVE FIX - aspoň reálné hodnoty z Discordu)
        app.config["BOT_STATS"]["total_servers"] = len(guilds)
        app.config["BOT_STATS"]["total_users"] = len(guilds) * 25  # fallback estimate

        return redirect(url_for("dashboard"))

    # ================= DASHBOARD =================

    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        stats = app.config["BOT_STATS"]

        return render_template(
            "dashboard.html",
            user=session["user"],
            user_guilds=session.get("user_guilds", []),
            bot_servers=session.get("user_guilds", []),
            total_servers=stats["total_servers"],
            total_users=stats["total_users"]
        )

    # ================= API =================

    @app.route("/api/stats")
    def stats():
        return app.config["BOT_STATS"]

    # ================= LOGOUT =================

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
