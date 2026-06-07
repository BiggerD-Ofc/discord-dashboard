"""
Configuration settings for the dashboard.
"""
import os
from urllib.parse import urlparse

class Config:
    # Base configuration
    DEBUG = os.getenv('FLASK_ENV', 'development') == 'development'
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-12345-change-this-in-production')
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = './.flask_session/'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 604800  # 7 days in seconds
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # OAuth2 configuration
    OAUTHLIB_INSECURE_TRANSPORT = DEBUG  # Allow HTTP in development
    OAUTHLIB_RELAX_TOKEN_SCOPE = True
    
    # Allowed domains (without port)
    ALLOWED_DOMAINS = [
        '127.0.0.1',
        'localhost',
        'dash.quanty-bot.linkpc.net'
    ]
    
    # Default redirect URIs (used as fallback)
    DEFAULT_REDIRECT_URIS = [
        'http://127.0.0.1:5001/callback',
        'http://localhost:5001/callback',
        'https://dash.quanty-bot.linkpc.net:5001/callback'
    ]
    
    # Required OAuth2 scopes
    DISCORD_OAUTH_SCOPES = ['identify', 'email', 'guilds']
    
    # Get redirect URIs from environment or use defaults
    _redirect_uris = os.getenv('DISCORD_REDIRECT_URIS', '')
    DISCORD_REDIRECT_URIS = [
        uri.strip() for uri in _redirect_uris.split(',') if uri.strip()
    ] if _redirect_uris else DEFAULT_REDIRECT_URIS
    
    # Primary redirect URI (first in the list)
    DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 
                                  DISCORD_REDIRECT_URIS[0] if DISCORD_REDIRECT_URIS else DEFAULT_REDIRECT_URIS[0])
    
    # Discord OAuth2 credentials
    DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '1256909611341189193')
    DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', 'dev-client-secret')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN', '')
    
    # Discord OAuth2 settings (override in environment)
    DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '1256909611341189193')
    DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    DISCORD_REDIRECT_URI = os.getenv('https://dash.quanty-bot.linkpc.net/callback')
    
    @classmethod
    def get_redirect_uri(cls, request_host):
        """
        Get the appropriate redirect URI based on the request host.
        Tries to match the request host with one of the allowed URIs.
        """
        if not request_host:
            return cls.DISCORD_REDIRECT_URI
            
        # Extract host without port for comparison
        request_host = request_host.split(':')[0] if ':' in request_host else request_host
        
        # Try to find a matching URI in the allowed list
        for uri in cls.DISCORD_REDIRECT_URIS:
            uri_host = urlparse(uri).netloc.split(':')[0]
            if request_host == uri_host or request_host in cls.ALLOWED_DOMAINS:
                return uri
        
        # If no match found, use the primary URI
        return cls.DISCORD_REDIRECT_URI

# Create config instance
config = Config()
