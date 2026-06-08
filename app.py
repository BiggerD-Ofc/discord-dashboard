import os
import requests
from flask import Flask, render_template, redirect, url_for, session, request, jsonify

CLIENT_ID = "1256909611341189193"
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://dash.quanty-bot.linkpc.net/callback")

OAUTH = (
    "https://discord.com/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    "&response_type=code"
    f"&redirect_uri={REDIRECT_URI}"
    "&scope=identify%20guilds"
)

TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"
GUILDS_URL = "https://discord.com/api/users/@me/guilds"


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev")

    # ---------------- HOME ----------------
    @app.route("/")
    def home():
        return redirect(url_for("dashboard")) if "user" in session else redirect(url_for("login"))

    # ---------------- LOGIN ----------------
    @app.route("/login")
    def login():
        return redirect(OAUTH)

    # ---------------- CALLBACK (SAFE MODE) ----------------
    @app.route("/callback")
    def callback():
        try:
            code = request.args.get("code")
            if not code:
                return "No code", 400

            if not CLIENT_SECRET:
                return "Missing DISCORD_CLIENT_SECRET", 500

            data = {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            token_res = requests.post(TOKEN_URL, data=data, headers=headers).json()
            access_token = token_res.get("access_token")

            if not access_token:
                return jsonify(token_res), 400

            auth = {"Authorization": f"Bearer {access_token}"}

            user = requests.get(USER_URL, headers=auth).json()
            guilds = requests.get(GUILDS_URL, headers=auth).json()

            if not isinstance(guilds, list):
                guilds = []

            avatar = user.get("avatar")
            uid = user.get("id")

            avatar_url = (
                f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png"
                if avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
            )

            session["user"] = {
                "id": uid,
                "username": user.get("username", "Unknown"),
                "avatar": avatar_url
            }

            servers = []
            total_users = 0

            for g in guilds:
                count = g.get("approximate_member_count") or 0
                try:
                    count = int(count)
                except:
                    count = 0

                servers.append({
                    "id": g.get("id"),
                    "name": g.get("name"),
                    "icon": g.get("icon"),
                    "members": count
                })

                total_users += count

            session["guilds"] = servers
            session["stats"] = {
                "total_servers": len(servers),
                "total_users": total_users
            }

            return redirect(url_for("dashboard"))

        except Exception as e:
            return f"SERVER ERROR: {str(e)}", 500

    # ---------------- DASHBOARD ----------------
    @app.route("/dashboard")
    def dashboard():
        if "user" not in session:
            return redirect(url_for("login"))

        stats = session.get("stats") or {}

        return render_template(
            "dashboard.html",
            user=session["user"],
            user_guilds=session.get("guilds", []),
            total_servers=stats.get("total_servers", 0),
            total_users=stats.get("total_users", 0)
        )

    # ---------------- API ----------------
    @app.route("/api/stats")
    def api_stats():
        return jsonify(session.get("stats", {"total_servers": 0, "total_users": 0}))

    @app.route("/api/servers")
    def api_servers():
        return jsonify(session.get("guilds", []))

    # ---------------- LOGOUT ----------------
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
