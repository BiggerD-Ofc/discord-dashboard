import os
import requests
from flask import Flask, render_template, redirect, url_for, session

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

API = "https://discord.com/api"

def get_bot_guilds():
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    r = requests.get(f"{API}/users/@me/guilds", headers=headers)
    return r.json() if r.status_code == 200 else []

def get_total_users(guilds):
    total = 0
    for g in guilds:
        if "approximate_member_count" in g:
            total += g["approximate_member_count"]
        elif "member_count" in g:
            total += g["member_count"]
    return total


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev")

    @app.route("/")
    def home():
        if "user" in session:
            return redirect("/dashboard")
        return redirect("/login")

    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect("/login")

        guilds = get_bot_guilds()

        total_servers = len(guilds)
        total_users = get_total_users(guilds)

        user = session["user"]

        return render_template(
            "dashboard.html",
            user=user,
            user_guilds=[],
            bot_servers=guilds,
            total_servers=total_servers,
            total_users=total_users
        )

    @app.route("/api/stats")
    def stats():
        guilds = get_bot_guilds()
        return {
            "total_servers": len(guilds),
            "total_users": get_total_users(guilds)
        }

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
