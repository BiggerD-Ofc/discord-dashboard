import os
import logging
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for, session, request
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

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

    # =====================
    # HOME
    # =====================
    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    # =====================
    # LOGIN
    # =====================
    @app.route("/login")
    def login():
        return redirect(OAUTH_URL)

    # =====================
    # CALLBACK
    # =====================
    @app.route("/callback")
    def callback():
        code = request.args.get("code")
        if not code:
            return "Missing code", 400

        token_res = requests.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        token_json = token_res.json()
        access_token = token_json.get("access_token")

        if not access_token:
            return f"Token error: {token_json}", 400

        user = requests.get(
            USER_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        ).json()

        session["user"] = {
            "id": user.get("id"),
            "username": user.get("username"),
            "avatar": user.get("avatar")
        }

        session["access_token"] = access_token

        return redirect(url_for("dashboard"))

    # =====================
    # DASHBOARD (LIVE DATA)
    # =====================
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        access_token = session.get("access_token")

        guilds = []
        admin_guilds = []

        if access_token:
            try:
                guilds = requests.get(
                    GUILDS_URL,
                    headers={"Authorization": f"Bearer {access_token}"}
                ).json()

                if not isinstance(guilds, list):
                    guilds = []

                for g in guilds:
                    perms = int(g.get("permissions", 0))
                    if perms & 0x8:
                        admin_guilds.append(g)

            except Exception as e:
                logger.error(f"Guild fetch error: {e}")

        return render_template(
            "dashboard.html",
            user=session.get("user", {}),
            total_servers=len(guilds),
            total_users=len(guilds),  # fallback (Discord nedává member count)
            user_guilds=admin_guilds,
            bot_servers=[]
        )

    # =====================
    # SERVERS (FIX URL ERROR)
    # =====================
    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect(url_for("home"))

        return render_template(
            "servers.html",
            user=session.get("user", {}),
            user_guilds=[],
            bot_servers=[]
        )

    # =====================
    # API
    # =====================
    @app.route("/api/stats")
    def stats():
        access_token = session.get("access_token")

        if not access_token:
            return {"total_servers": 0, "total_users": 0}

        try:
            guilds = requests.get(
                GUILDS_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            ).json()

            if not isinstance(guilds, list):
                guilds = []

            admin = [g for g in guilds if int(g.get("permissions", 0)) & 0x8]

            return {
                "total_servers": len(guilds),
                "total_users": len(guilds),
                "admin_servers": len(admin)
            }

        except:
            return {"total_servers": 0, "total_users": 0}

    # =====================
    # LOGOUT
    # =====================
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
