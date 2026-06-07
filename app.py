import os
import logging
from datetime import timedelta
from flask import Flask, render_template, redirect, url_for, session, jsonify
from flask_discord import DiscordOAuth2Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")


def create_app():
    app = Flask(__name__, static_folder="static")

    # =====================
    # CONFIG
    # =====================
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
    app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
    app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")

    app.config["DISCORD_SCOPE"] = ["identify", "email", "guilds"]

    # =====================
    # DISCORD
    # =====================
    discord = DiscordOAuth2Session(app)
    app.extensions["discord"] = discord

    # =====================
    # ROUTES
    # =====================

    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/login")
    def login():
        session.clear()
        return discord.create_session(scope=app.config["DISCORD_SCOPE"])

    @app.route("/callback")
    def callback():
        discord.callback()
        user = discord.fetch_user()

        session["user"] = {
            "id": str(user.id),
            "name": user.name,
            "avatar": user.avatar_url if hasattr(user, "avatar_url") else None
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
        return render_template("dashboard.html", user=session["user"])

    @app.route("/servers")
    def servers():
        if "user" not in session:
            return redirect(url_for("home"))
        return render_template("servers.html", user=session["user"])

    @app.route("/api/stats")
    def stats():
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
