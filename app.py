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


def create_app():
    app = Flask(__name__, static_folder="static")

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/login")
    def login():
        return redirect(OAUTH_URL)

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

        token_response = requests.post(
            TOKEN_URL,
            data=data,
            headers=headers
        )

        token_json = token_response.json()

        access_token = token_json.get("access_token")

        if not access_token:
            return f"Token error: {token_json}", 400

        user_response = requests.get(
            USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )

        user = user_response.json()

        avatar_url = None
        if user.get("avatar"):
            avatar_url = (
                f"https://cdn.discordapp.com/avatars/"
                f"{user['id']}/{user['avatar']}.png"
            )

        session["user"] = {
            "id": user["id"],
            "username": user["username"],
            "discriminator": user.get("discriminator", "0000"),
            "email": user.get("email"),
            "avatar": avatar_url
        }

        return redirect(url_for("dashboard"))

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("home"))

        return render_template(
            "dashboard.html",
            user=session["user"],
            total_users=0,
            total_servers=0,
            user_guilds=[],
            bot_servers=[]
        )

    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect(url_for("home"))

        return render_template(
            "servers.html",
            user=session["user"]
        )

    @app.route("/api/stats")
    def stats():
        return {
            "status": "ok",
            "total_users": 0,
            "total_servers": 0
        }

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port
    )
