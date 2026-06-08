import os
import logging
import time
import requests
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for, session, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

# =========================
# ENV
# =========================
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://dash.quanty-bot.linkpc.net/callback"
)

# =========================
# OAUTH URL
# =========================
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

# =========================
# CACHE
# =========================
CACHE = {
    "time": 0,
    "data": {}
}
CACHE_TTL = 30

# =========================
# APP
# =========================
def create_app():
    app = Flask(__name__, static_folder="static")

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    # =========================
    # HELPERS
    # =========================
    def get_bot_guilds():
        if not BOT_TOKEN:
            return []

        r = requests.get(
            GUILDS_URL,
            headers={"Authorization": f"Bot {BOT_TOKEN}"}
        )

        if r.status_code != 200:
            return []

        return r.json()

    def get_total_users():
        guilds = get_bot_guilds()
        return sum(g.get("approximate_member_count", 0) for g in guilds)

    def get_admin_servers():
        guilds = get_bot_guilds()

        admins = []
        for g in guilds:
            perms = int(g.get("permissions", 0))
            if perms & 0x8:  # ADMINISTRATOR
                admins.append(g)

        return admins

    def get_stats():
        now = time.time()

        if CACHE["data"] and now - CACHE["time"] < CACHE_TTL:
            return CACHE["data"]

        guilds = get_bot_guilds()

        data = {
            "total_servers": len(guilds),
            "total_users": get_total_users(),
            "admin_servers": len(get_admin_servers())
        }

        CACHE["data"] = data
        CACHE["time"] = now

        return data

    # =========================
    # ROUTES
    # =========================

    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    # LOGIN
    @app.route("/login")
    def login():
        session.clear()
        return redirect(OAUTH_URL)

    # CALLBACK
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

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        token = requests.post(TOKEN_URL, data=data, headers=headers).json()

        access_token = token.get("access_token")

        if not access_token:
            return f"Token error: {token}", 400

        user = requests.get(
            USER_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        ).json()

        session["user"] = {
            "id": user["id"],
            "name": user["username"],
            "avatar": user.get("avatar")
        }

        return redirect(url_for("dashboard"))

    # LOGOUT
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    # DASHBOARD
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        stats = get_stats()

        return render_template(
            "dashboard.html",
            user=session["user"],
            total_servers=stats["total_servers"],
            total_users=stats["total_users"],
            admin_servers=stats["admin_servers"],
            user_guilds=get_admin_servers(),
            bot_servers=get_bot_guilds()
        )

    # SERVERS
    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect(url_for("home"))

        return render_template("servers.html", user=session["user"])

    # API STATS
    @app.route("/api/stats")
    def api_stats():
        return get_stats()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
