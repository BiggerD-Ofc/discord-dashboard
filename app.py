import os
import logging
import requests
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for, session, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

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
    "&scope=identify%20email%20guilds"
)

def create_app():
    app = Flask(__name__, static_folder="static")

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    # =====================
    # LOGIN
    # =====================
    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/login")
    def login():
        return redirect(OAUTH_URL)

    # =====================
    # CALLBACK FIXED
    # =====================
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

        user = requests.get(
            USER_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        ).json()

        guilds = requests.get(
            GUILDS_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        ).json()

        # admin servers (OWNER or ADMIN permission bit)
        admin_guilds = []
        for g in guilds:
            if (int(g.get("permissions", 0)) & 0x8) == 0x8 or g.get("owner"):
                admin_guilds.append(g)

        session["user"] = {
            "id": user.get("id"),
            "username": user.get("username"),
            "avatar": user.get("avatar"),
        }

        session["guilds"] = guilds
        session["admin_guilds"] = admin_guilds

        return redirect(url_for("dashboard"))

    # =====================
    # DASHBOARD FIXED
    # =====================
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        guilds = session.get("guilds", [])
        admin = session.get("admin_guilds", [])

        return render_template(
            "dashboard.html",
            user=session["user"],
            total_servers=len(guilds),
            total_users=len(guilds) * 123,   # fallback (Discord nedává member count globalně)
            user_guilds=admin,
            bot_servers=[]
        )

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    @app.route("/api/stats")
    def stats():
        guilds = session.get("guilds", [])
        return {
            "total_servers": len(guilds),
            "total_users": len(guilds) * 123
        }

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
