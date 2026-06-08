import os
import logging
import requests
import time
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
# DISCORD OAUTH
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
# CACHE (anti rate-limit)
# =========================
CACHE = {
    "time": 0,
    "stats": {}
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

    def get_stats():
        now = time.time()

        if CACHE["stats"] and now - CACHE["time"] < CACHE_TTL:
            return CACHE["stats"]

        guilds = get_bot_guilds()

        total_servers = len(guilds)
        total_users = sum(
            g.get("approximate_member_count", 0) for g in guilds
        )

        data = {
            "total_servers": total_servers,
            "total_users": total_users
        }

        CACHE["stats"] = data
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

    # CALLBACK (FIXED)
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

        token_response = requests.post(TOKEN_URL, data=data, headers=headers)
        token_json = token_response.json()

        access_token = token_json.get("access_token")

        if not access_token:
            return f"Token error: {token_json}", 400

        user_response = requests.get(
            USER_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

        user = user_response.json()

        session["user"] = {
            "id": user["id"],
            "name": user["username"],
            "avatar": user.get("avatar"),
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
            total_users=stats["total_users"]
        )

    # SERVERS
    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect(url_for("home"))

        return render_template("servers.html", user=session["user"])

    # API STATS (LIVE)
    @app.route("/api/stats")
    def api_stats():
        return get_stats()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
