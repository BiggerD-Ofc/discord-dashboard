import os
import logging
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for, session, request
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1256909611341189193")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://dash.quanty-bot.linkpc.net/callback")

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


def avatar_url(user_id, avatar):
    if avatar:
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png"
    return "https://cdn.discordapp.com/embed/avatars/0.png"


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
    # CALLBACK (FIXED)
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

        token_res = requests.post(TOKEN_URL, data=data, headers=headers)
        token_json = token_res.json()

        access_token = token_json.get("access_token")
        if not access_token:
            logger.error(f"Token error: {token_json}")
            return f"Token error: {token_json}", 400

        auth = {"Authorization": f"Bearer {access_token}"}

        user_res = requests.get(USER_URL, headers=auth)
        user = user_res.json()

        guilds_res = requests.get(GUILDS_URL, headers=auth)
        guilds = guilds_res.json()

        # admin servers = OWNER nebo ADMIN permission (bit 0x8)
        admin_guilds = []
        for g in guilds:
            perms = int(g.get("permissions", 0))
            if perms & 0x8 or g.get("owner"):
                admin_guilds.append(g)

        session["user"] = {
            "id": user["id"],
            "username": user["username"],
            "discriminator": user.get("discriminator", "0"),
            "avatar": avatar_url(user["id"], user.get("avatar")),
            "email": user.get("email"),
        }

        session["guilds"] = guilds
        session["admin_guilds"] = admin_guilds

        return redirect(url_for("dashboard"))

    # =====================
    # DASHBOARD (FIXED SAFE)
    # =====================
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        guilds = session.get("guilds", [])
        admin_guilds = session.get("admin_guilds", [])

        return render_template(
            "dashboard.html",
            user=session["user"],
            user_guilds=admin_guilds,
            bot_servers=guilds,
            total_servers=len(guilds),
            total_users=sum(int(g.get("approximate_member_count", 0) or 0) for g in guilds)
        )

    # =====================
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    # =====================
    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect(url_for("home"))
        return render_template("servers.html", user=session["user"])

    # =====================
    @app.route("/api/stats")
    def stats():
        guilds = session.get("guilds", [])
        return {
            "total_servers": len(guilds),
            "total_users": sum(int(g.get("approximate_member_count", 0) or 0) for g in guilds)
        }

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
