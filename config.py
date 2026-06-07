"""
Configuration settings for the dashboard.
"""
import os
from urllib.parse import urlparse


class Config:
    # =========================
    # BASE
    # =========================
    DEBUG = os.getenv('FLASK_ENV', 'development') == 'development'
    SECRET_KEY = os.getenv(
        'SECRET_KEY',
        'dev-secret-key-12345-change-this-in-production'
    )

    # =========================
    # SESSION
    # =========================
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = './.flask_session/'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 604800  # 7 days
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # =========================
    # OAUTH SETTINGS
    # =========================
    OAUTHLIB_INSECURE_TRANSPORT = DEBUG
    OAUTHLIB_RELAX_TOKEN_SCOPE = True

    DISCORD_OAUTH_SCOPES = ['identify', 'email', 'guilds']

    # =========================
    # REDIRECT URIS
    # =========================
    DEFAULT_REDIRECT_URIS = [
        'http://127.0.0.1:5001/callback',
        'http://localhost:5001/callback',
        'https://dash.quanty.linkpc.net/callback'
    ]

    _redirect_uris = os.getenv('DISCORD_REDIRECT_URIS', '')

    DISCORD_REDIRECT_URIS = [
        uri.strip()
        for uri in _redirect_uris.split(',')
        if uri.strip()
    ] if _redirect_uris else DEFAULT_REDIRECT_URIS

    DISCORD_REDIRECT_URI = os.getenv(
        'DISCORD_REDIRECT_URI',
        DISCORD_REDIRECT_URIS[0]
    )

    # =========================
    # DISCORD CREDENTIALS
    # =========================
    DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
    DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN')

    # =========================
    # DOMAIN CONTROL
    # =========================
    ALLOWED_DOMAINS = [
        '127.0.0.1',
        'localhost',
        'dash.quanty.linkpc.net'
    ]

    @classmethod
    def get_redirect_uri(cls, request_host):
        if not request_host:
            return cls.DISCORD_REDIRECT_URI

        request_host = request_host.split(':')[0]

        for uri in cls.DISCORD_REDIRECT_URIS:
            uri_host = urlparse(uri).netloc.split(':')[0]
            if request_host == uri_host or request_host in cls.ALLOWED_DOMAINS:
                return uri

        return cls.DISCORD_REDIRECT_URI


config = Config()
