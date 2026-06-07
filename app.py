import os
import logging
import requests
import traceback
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from flask import (
    Flask, render_template, redirect, url_for, session,
    jsonify, request
)
from flask_discord import DiscordOAuth2Session

# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

file_handler = RotatingFileHandler(
    'dashboard.log',
    maxBytes=10 * 1024 * 1024,
    backupCount=5
)
logger.addHandler(file_handler)

# =========================
# Load env
# =========================
load_dotenv()

from dashboard.config import config


# =========================
# APP FACTORY
# =========================
def create_app(env="production"):
    app = Flask(__name__, static_folder='static')

    # =========================
    # Basic config
    # =========================
    app.config.from_object(config)
    app.config['ENV'] = env
    app.config['DEBUG'] = env == "development"

    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "change-me"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7)
    )

    # =========================
    # OAuth config
    # =========================
    app.config['DISCORD_CLIENT_ID'] = config.DISCORD_CLIENT_ID
    app.config['DISCORD_CLIENT_SECRET'] = config.DISCORD_CLIENT_SECRET
    app.config['DISCORD_REDIRECT_URI'] = config.DISCORD_REDIRECT_URI
    app.config['DISCORD_SCOPE'] = ['identify', 'email', 'guilds']

    # =========================
    # Discord OAuth init
    # =========================
    discord = DiscordOAuth2Session(app)
    app.extensions['discord'] = discord

    # =========================
    # ROUTES
    # =========================

    @app.route("/")
    def home():
        if "user" in session:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/login")
    def login():
        session.clear()

        discord = app.extensions["discord"]

        auth_url = discord.authorization_url(
            scope=app.config["DISCORD_SCOPE"],
            redirect_uri=app.config["DISCORD_REDIRECT_URI"]
        )

        return redirect(auth_url)

    @app.route("/callback")
    def callback():
        discord = app.extensions["discord"]

        try:
            token = discord.token
            user = discord.user

            session["discord_token"] = token
            session["user"] = {
                "id": str(user.id),
                "name": user.name,
                "avatar": getattr(user, "avatar_url", None)
            }

            return redirect(url_for("dashboard"))

        except Exception as e:
            logger.error(f"OAuth error: {e}")
            return "Auth failed", 500

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

    # =========================
    # API
    # =========================

    @app.route("/api/stats")
    def api_stats():
        return jsonify({
            "status": "ok"
        })

    # =========================
    # ERROR HANDLERS
    # =========================

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", error="404 Not Found"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", error="500 Server Error"), 500

    return app


# =========================
# RUN (RENDER SAFE)
# =========================
if __name__ == "__main__":
    app = create_app("development")

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )