import os
import requests
from flask import Flask, render_template, redirect, session, request

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
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


def get_user_guilds(token):
    if not token:
        return []
    try:
        r = requests.get(GUILDS_URL, headers={"Authorization": f"Bearer {token}"})
        return r.json() if r.status_code == 200 else []
    except:
        return []


def get_bot_guilds():
    if not BOT_TOKEN:
        return []
    try:
        r = requests.get(GUILDS_URL, headers={"Authorization": f"Bot {BOT_TOKEN}"})
        return r.json() if r.status_code == 200 else []
    except:
        return []


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-key")

    @app.route("/")
    def home():
        if "user" in session:
            return redirect("/dashboard")
        return redirect("/login")

    @app.route("/login")
    def login():
        return redirect(OAUTH_URL)

    @app.route("/callback")
    def callback():
        code = request.args.get("code")
        if not code:
            return "Missing code", 400

        token_response = requests.post(
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
            "id": user.get("id"),
            "username": user.get("username", "Unknown"),
            "avatar": user.get("avatar")
        }

        session["access_token"] = access_token

        return redirect("/dashboard")

    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect("/login")

        token = session.get("access_token")

        user_guilds = get_user_guilds(token)

        # FIX ADMIN SERVERS (SAFE)
        admin_guilds = []
        for g in user_guilds:
            try:
                perms = int(g.get("permissions") or 0)
                if perms & 0x8:
                    admin_guilds.append(g)
            except:
                pass

        bot_guilds = get_bot_guilds()

        return render_template(
            "dashboard.html",
            user=session["user"],
            user_guilds=admin_guilds,
            bot_servers=bot_guilds,
            total_servers=len(bot_guilds),
            total_users=len(bot_guilds)
        )

    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect("/login")

        return render_template(
            "servers.html",
            user=session["user"],
            user_guilds=get_user_guilds(session.get("access_token")),
            bot_servers=[]
        )

    @app.route("/api/stats")
    def stats():
        bot_guilds = get_bot_guilds()
        return {
            "total_servers": len(bot_guilds),
            "total_users": len(bot_guilds)
        }

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect("/")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
