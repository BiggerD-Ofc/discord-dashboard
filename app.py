import os
import logging
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

# =========================
# CONFIG (MUSÍ SEDĚT S DISCORDEM)
# =========================
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://dash.quanty-bot.linkpc.net/callback"
)

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
# APP
# =========================
def create_app():
    app = Flask(__name__, static_folder="static")

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    # =========================
    # HOME
    # =========================
    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    # =========================
    # LOGIN
    # =========================
    @app.route("/login")
    def login():
        return redirect(OAUTH_URL)

    # =========================
    # CALLBACK (FIXED)
    # =========================
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

        token_res = requests.post(TOKEN_URL, data=data, headers=headers)
        token_json = token_res.json()

        access_token = token_json.get("access_token")
        if not access_token:
            logger.error(token_json)
            return f"Token error: {token_json}", 400

        # USER
        user_res = requests.get(
            USER_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user = user_res.json()

        # GUILDS (pro statistiky)
        guilds_res = requests.get(
            GUILDS_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        guilds = guilds_res.json()

        # ADMIN servers (permission bit 0x8)
        admin_guilds = []
        total_users = 0

        for g in guilds:
            perms = int(g.get("permissions", 0))

            # admin bit
            if perms & 0x8:
                admin_guilds.append({
                    "id": g["id"],
                    "name": g["name"],
                    "icon_url": (
                        f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png"
                        if g.get("icon") else None
                    ),
                    "member_count": g.get("approximate_member_count", 0)
                })

            total_users += g.get("approximate_member_count", 0)

        session["access_token"] = access_token
        session["user"] = {
            "id": user["id"],
            "username": user["username"],
            "discriminator": user.get("discriminator", "0"),
            "avatar": user.get("avatar"),
        }

        session["stats"] = {
            "total_servers": len(guilds),
            "total_users": total_users,
            "admin_servers": len(admin_guilds),
            "admin_guilds": admin_guilds
        }

        return redirect(url_for("dashboard"))

    # =========================
    # DASHBOARD
    # =========================
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        stats = session.get("stats", {})

        return render_template(
            "dashboard.html",
            user=session["user"],
            total_servers=stats.get("total_servers", 0),
            total_users=stats.get("total_users", 0),
            user_guilds=stats.get("admin_guilds", []),
            bot_servers=[]
        )

    # =========================
    # API STATS (LIVE FIX)
    # =========================
    @app.route("/api/stats")
    def stats():
        stats = session.get("stats", {})
        return jsonify({
            "total_servers": stats.get("total_servers", 0),
            "total_users": stats.get("total_users", 0)
        })

    # =========================
    # LOGOUT
    # =========================
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
