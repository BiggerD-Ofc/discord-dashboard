import os
import sys
import logging
import requests
import json
import traceback
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse, urlunparse, urljoin
from dotenv import load_dotenv
from flask import (
    Flask, render_template, redirect, url_for, session,
    jsonify, request, flash, abort, current_app
)
from flask_discord import DiscordOAuth2Session, Unauthorized

# Configure logging before anything else
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables from .env file"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"Loaded environment variables from {env_path}")
    else:
        logger.warning(f"No .env file found at {env_path}")

# Load environment variables when this module is imported
load_environment()

# Import configuration after environment is loaded
from dashboard.config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up rotating file handler for logging
file_handler = RotatingFileHandler('dashboard.log', maxBytes=1024*1024*10, backupCount=20)
logger.addHandler(file_handler)

def create_app(env='development'):
    """Create and configure the Flask application."""
    # Create the Flask app
    app = Flask(__name__, static_folder='static', static_url_path='')
    
    # Set the environment
    app.config['ENV'] = env
    app.config['DEBUG'] = env == 'development'
    
    # Add favicon route
    @app.route('/favicon.ico')
    def favicon():
        return app.send_static_file('img/bot-logo.png')
    
    # Apply configuration
    app.config.from_object(config)
    
    # Set Flask configuration
    app.config['TRAP_HTTP_EXCEPTIONS'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = True
    
    # Configure OAuth2 for development
    if env == 'development':
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Enable for HTTP
        app.config['DEBUG'] = True
    else:
        app.config['DEBUG'] = False
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'  # Relax token scope checking
        app.config['PREFERRED_URL_SCHEME'] = 'http'  # Use HTTP in development
        app.config['SERVER_NAME'] = 'localhost:5001'  # Set server name for URL generation
    
    # Ensure session directory exists
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
    
    # Ensure session directory exists
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
    
    # Configure logging
    logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO)
    logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Log startup info
    logger.info(f"Starting Flask app in {env} mode")
    
    # Configure session
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', os.urandom(24).hex()),
        SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        SESSION_REFRESH_EACH_REQUEST=True
    )
    
    # Configure Discord OAuth2
    app.config.update(
        DISCORD_CLIENT_ID=config.DISCORD_CLIENT_ID,
        DISCORD_CLIENT_SECRET=config.DISCORD_CLIENT_SECRET,
        DISCORD_BOT_TOKEN=os.getenv('DISCORD_TOKEN', config.DISCORD_BOT_TOKEN),
        DISCORD_SCOPE=config.DISCORD_OAUTH_SCOPES,
        DISCORD_REDIRECT_URI=config.DISCORD_REDIRECT_URI,
        DISCORD_OAUTH_SCOPES=config.DISCORD_OAUTH_SCOPES
    )
    
    # Log the redirect URIs being used
    logger.info(f"Using redirect URI: {app.config['DISCORD_REDIRECT_URI']}")
    logger.info(f"Available redirect URIs: {getattr(config, 'DISCORD_REDIRECT_URIS', [])}")
    
    # Check for required configuration
    if not app.config.get('DISCORD_CLIENT_ID'):
        raise ValueError("DISCORD_CLIENT_ID environment variable is required")
    if not app.config.get('DISCORD_CLIENT_SECRET'):
        raise ValueError("DISCORD_CLIENT_SECRET environment variable is required")
    
    # Verify the redirect URI
    redirect_uri = app.config.get('DISCORD_REDIRECT_URI')
    if not redirect_uri or not (redirect_uri.startswith('http://') or redirect_uri.startswith('https://')):
        raise ValueError(f"Invalid redirect URI: {redirect_uri}. Must start with http:// or https://")
    
    # Log configuration
    logger.info(f"Starting in {env} mode")
    logger.info(f"Allowed domains: {config.ALLOWED_DOMAINS}")
    logger.info(f"Using Discord OAuth2 with client ID: {app.config['DISCORD_CLIENT_ID']}")
    logger.info(f"Using redirect URI: {redirect_uri}")
    logger.warning("WARNING: Running with default client secret in development mode. Use environment variables in production.")
    
    # Required OAuth2 scopes - add 'guilds' to get user's guilds
    app.config['DISCORD_SCOPE'] = ['identify', 'email', 'guilds']
    
    # Print OAuth2 configuration for debugging
    print(f"OAuth2 Configuration:")
    print(f"- Client ID: {app.config['DISCORD_CLIENT_ID']}")
    print(f"- Redirect URI: {redirect_uri}")
    print(f"- Scopes: {app.config['DISCORD_SCOPE']}")
    
    # Initialize Discord OAuth2 session
    try:
        # Ensure redirect URI is properly set
        redirect_uri = app.config['DISCORD_REDIRECT_URI']
        logger.info(f"Initializing Discord OAuth2 with redirect_uri: {redirect_uri}")
        
        # Initialize Discord OAuth2 session with correct parameters
        discord = DiscordOAuth2Session(app)
        
        # Configure OAuth2 settings
        discord.init_app(app)
        discord.client_id = app.config['DISCORD_CLIENT_ID']
        discord.client_secret = app.config['DISCORD_CLIENT_SECRET']
        discord.redirect_uri = redirect_uri
        
        # Set scopes for session
        discord.scope = app.config['DISCORD_SCOPE']
        
        # Store discord session in app context
        app.extensions['discord'] = discord
        logger.info("Discord OAuth2 session initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Discord OAuth2 session: {e}")
        raise
    
    @app.route('/logout')
    def logout():
        """Log the user out by clearing the session."""
        # Revoke the Discord token if it exists
        if 'discord_token' in session:
            try:
                # Revoke the Discord token
                token = session['discord_token']
                if 'access_token' in token:
                    revoke_url = 'https://discord.com/api/oauth2/token/revoke'
                    data = {
                        'token': token['access_token'],
                        'token_type_hint': 'access_token'
                    }
                    auth = (app.config['DISCORD_CLIENT_ID'], app.config['DISCORD_CLIENT_SECRET'])
                    requests.post(revoke_url, data=data, auth=auth)
            except Exception as e:
                logger.error(f"Error revoking token: {e}")
        
        # Clear the session
        session.clear()
        
        # Redirect to home page
        return redirect(url_for('home'))
    
    # Routes
    @app.route('/')
    def home():
        logger.info("Home route accessed")
        logger.debug(f"Session data: {dict(session)}")
        
        # Check if we have the required configuration
        if not app.config['DISCORD_CLIENT_SECRET']:
            error_msg = "Server configuration error: Missing Discord OAuth2 client secret"
            logger.error(error_msg)
            return render_template('error.html', 
                               error_message=error_msg,
                               error_code=500), 500
        
        # Check if user is already logged in via session
        if 'user' in session:
            logger.info(f"User found in session: {session['user'].get('username', 'Unknown')}")
            return redirect(url_for('dashboard'))
            
        # User is not logged in, show login page
        logger.info("No user in session, showing login page")
        return render_template('login.html', 
                           title="Login | Mr.Afton",
                           active_page='login')
    @app.route('/login')
    def login():
        """Redirect to Discord OAuth2 login."""
        try:
            logger.info("Login route accessed")
            
            # Get the Discord OAuth2 session from the app context
            discord = app.extensions.get('discord')
            if not discord:
                error_msg = "Discord OAuth2 session not initialized"
                logger.error(error_msg)
                return render_template('error.html', 
                                   error_message=error_msg,
                                   error_code=500), 500
            
            # Get the redirect URI and scopes from config
            redirect_uri = app.config['DISCORD_REDIRECT_URI']
            scopes = app.config['DISCORD_SCOPE']
            
            logger.info(f"Initiating OAuth2 flow with scopes: {scopes}")
            logger.info(f"Using redirect URI: {redirect_uri}")
            
            # Clear any existing state and tokens
            session.clear()
            logger.info("Cleared existing session data")
            
            # Generate authorization URL
            try:
                # Create a new OAuth2 session
                authorization_url, state = discord.authorization_url(
                    scope=scopes,
                    redirect_uri=redirect_uri,
                    prompt="none"  # Don't show consent screen if already authorized
                )
                logger.debug(f"Generated OAuth2 authorization URL: {authorization_url}")
                
                # Redirect to Discord's OAuth2 URL
                return redirect(authorization_url)
                
            except Exception as e:
                error_msg = f"Failed to generate OAuth2 URL: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return render_template('error.html', 
                                   error_message=error_msg,
                                   error_code=500), 500
            
            logger.info(f"Redirecting to Discord OAuth2 URL: {authorization_url}")
            
            return redirect(authorization_url)
            
        except Exception as e:
            error_msg = f"Unexpected error in login route: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return render_template('error.html', 
                               error_message=error_msg,
                               error_code=500), 500
    
    @app.route('/callback')
    def callback():
        """Handle OAuth2 callback from Discord."""
        logger.info("\n=== Callback Started ===")
        logger.info(f"Request URL: {request.url}")
        
        try:
            # Log session info for debugging
            logger.debug(f"Session at callback start: {dict(session)}")
            
            discord = app.extensions.get('discord')
            if not discord:
                error_msg = "Discord OAuth2 session not initialized"
                logger.error(error_msg)
                return render_template('error.html',
                                   error_message=error_msg,
                                   error_code=500), 500
            
            # Handle potential errors from Discord
            if 'error' in request.args:
                error = request.args.get('error', 'unknown_error')
                error_description = request.args.get('error_description', 'No error description provided')
                error_msg = f"Discord OAuth2 error: {error} - {error_description}"
                logger.error(error_msg)
                return render_template('error.html',
                                   error_message=f"Authentication failed: {error_description}",
                                   error_code=400), 400
            
            # Exchange the authorization code for a token
            try:
                logger.info("Exchanging authorization code for token...")
                token = discord.token  # flask-discord automatically handles token exchange
                
                if not token:
                    error_msg = "Failed to obtain access token from Discord"
                    logger.error(error_msg)
                    return render_template('error.html',
                                       error_message=error_msg,
                                       error_code=500), 500
                
                # Store the token in the session
                session['discord_token'] = token
                session.permanent = True
                session.modified = True
                
                logger.debug("Token obtained, fetching user data...")
                
                # Fetch user data
                user = discord.user  # flask-discord automatically fetches user data
                if not user:
                    error_msg = "Failed to fetch user data from Discord"
                    logger.error(error_msg)
                    return render_template('error.html',
                                       error_message=error_msg,
                                       error_code=500), 500
                
                # Store minimal user data in session
                session['user'] = {
                    'id': str(user.id),
                    'name': user.name,
                    'discriminator': user.discriminator,
                    'avatar': user.avatar_url if hasattr(user, 'avatar_url') else None,
                    'email': getattr(user, 'email', None)
                }
                
                logger.info(f"Successfully authenticated user: {user.name}#{user.discriminator} ({user.id})")
                
                # Redirect to the dashboard
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                error_msg = f"Error during token exchange: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                return render_template('error.html',
                                   error_message=error_msg,
                                   error_code=500), 500
            
        except Exception as e:
            error_msg = f"Unexpected error in callback: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return render_template('error.html',
                               error_message=error_msg,
                               error_code=500), 500
    
    # API endpoints
    @app.route('/api/stats')
    def api_stats():
        try:
            if 'user' not in session or 'discord_token' not in session:
                return jsonify({"error": "Unauthorized"}), 401
                
            # Get bot instance
            from bot import bot
            
            # Calculate uptime if available
            uptime = '0d 0h 0m'
            if hasattr(bot, 'start_time'):
                uptime_seconds = (datetime.datetime.utcnow() - bot.start_time).total_seconds()
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                uptime = f"{days}d {hours}h {minutes}m"
            
            return jsonify({
                'total_servers': len(bot.guilds) if hasattr(bot, 'guilds') else 0,
                'total_users': len(bot.users) if hasattr(bot, 'users') else 0,
                'uptime': uptime,
                'commands_processed': 0  # You can track this if needed
            })
            
        except Exception as e:
            logger.error(f"Error in api_stats: {str(e)}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500
    
    @app.route('/dashboard')
    def dashboard():
        logger.info("\n=== Dashboard Route Accessed ===")
        
        try:
            # Check if user is authenticated
            if 'user' not in session or 'discord_token' not in session:
                logger.warning("Unauthenticated access to dashboard, redirecting to login")
                return redirect(url_for('login'))
                
            user = session['user']
            logger.info(f"Displaying dashboard for user: {user.get('username', 'Unknown')}")
            
            # Initialize empty lists for guilds and servers
            user_guilds = []
            bot_servers = []
            total_users = 0
            total_servers = 0
            
            try:
                # Get user's guilds from Discord API
                headers = {
                    'Authorization': f"Bearer {session['discord_token']['access_token']}"
                }
                user_guilds_response = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
                user_guilds_response.raise_for_status()
                user_guilds = user_guilds_response.json()
                
                # Filter guilds where user has admin permissions
                user_guilds = [guild for guild in user_guilds if (int(guild.get('permissions', 0)) & 0x8) == 0x8]
                
                # Get bot's guilds if available - using direct API instead of bot instance
                try:
                    from bot import bot
                    # Get guild info with icons
                    bot_servers = []
                    for guild in bot.guilds:
                        # Construct icon URL if available
                        icon_url = None
                        if guild.icon:
                            icon_url = f"https://cdn.discordapp.com/icons/{guild.id}/{guild.icon}.png?size=256"
                        
                        bot_servers.append({
                            'id': str(guild.id),
                            'name': guild.name,
                            'icon_url': icon_url,
                            'member_count': guild.member_count,
                            'created_at': guild.created_at.strftime('%Y-%m-%d %H:%M:%S') if guild.created_at else 'Unknown'
                        })
                    
                    # Calculate total users across all guilds (unique members)
                    unique_members = set()
                    for guild in bot.guilds:
                        for member in guild.members:
                            unique_members.add(member.id)
                    total_users = len(unique_members)
                    total_servers = len(bot.guilds)
                    
                except Exception as e:
                    logger.error(f"Error getting bot guilds: {str(e)}")
                    bot_servers = []
                
            except Exception as e:
                logger.error(f"Error getting user guilds: {str(e)}")
            
            # Prepare template context
            context = {
                'user': user,
                'user_guilds': user_guilds,
                'bot_servers': bot_servers,
                'total_users': total_users,
                'total_servers': total_servers,
                'title': 'Dashboard | Mr.Afton',
                'active_page': 'dashboard',
                'navigation': [
                    {"name": "Dashboard", "url": url_for('dashboard'), "icon": "fas fa-home"},
                    {"name": "Server Management", "url": url_for('servers'), "icon": "fas fa-server"}
                ]
            }
            
            return render_template('dashboard.html', **context)
            
        except Exception as e:
            logger.error(f"Error in dashboard route: {str(e)}", exc_info=True)
            # Provide minimal context for error template
            return render_template('error.html',
                               error_message="An error occurred while loading the dashboard.",
                               error_code=500,
                               user=session.get('user')), 500
    
    @app.route('/servers')
    def servers():
        logger.info("\n=== Servers Route Accessed ===")
        
        try:
            # Check if user is authenticated
            if 'user' not in session or 'discord_token' not in session:
                logger.warning("Unauthenticated access to servers, redirecting to login")
                return redirect(url_for('login'))
                
            user = session['user']
            logger.info(f"Displaying servers for user: {user.get('username', 'Unknown')}")
            
            return render_template('servers.html',
                               user=user,
                               title="Server Management | Mr.Afton",
                               active_page='servers')
            
        except Exception as e:
            logger.error(f"Error in servers route: {str(e)}", exc_info=True)
            return render_template('error.html',
                               error_message=f"Failed to load server management: {str(e)}",
                               error_code=500), 500
    
    @app.route('/api/servers')
    def get_servers():
        try:
            # Check if user is authenticated
            if 'discord_token' not in session:
                return jsonify({'error': 'Not authenticated'}), 401
                
            # In a real app, you would fetch the user's servers from the Discord API
            # and cross-reference with where your bot is present
            try:
                # This would be the actual implementation:
                # 1. Get user's guilds from Discord
                # headers = {
                #     'Authorization': f"Bearer {session['discord_token']['access_token']}"
                # }
                # user_guilds_response = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
                # user_guilds_response.raise_for_status()
                # user_guilds = user_guilds_response.json()
                
                # 2. Get bot's guilds from your database
                # bot_guilds = get_bot_guilds()  # Implement this function to get guilds where your bot is present
                
                # 3. Return intersection of user guilds where bot is present and user has manage guild permission
                # servers = [
                #     guild for guild in user_guilds 
                #     if guild['id'] in [bot_guild['id'] for bot_guild in bot_guilds] and
                #     (int(guild.get('permissions', 0)) & 0x20) == 0x20  # MANAGE_GUILD permission
                # ]
                
                # Mock response for demo purposes
                mock_servers = [
                    {
                        'id': '123456789012345678',
                        'name': 'Test Server 1',
                        'icon': 'abc123',
                        'owner': True,
                        'permissions': 2147483647,
                        'member_count': 42,
                        'bot_owner': True
                    },
                    {
                        'id': '987654321098765432',
                        'name': 'Test Server 2',
                        'icon': None,
                        'owner': False,
                        'permissions': 2147483647,
                        'member_count': 128,
                        'bot_owner': False
                    }
                ]
                
                return jsonify(mock_servers)
                
            except Exception as e:
                logger.error(f"Error fetching servers: {str(e)}", exc_info=True)
                return jsonify({'error': 'Failed to fetch servers from Discord API'}), 500
                
        except Exception as e:
            logger.error(f"Error in get_servers: {str(e)}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    
    # Error handlers
    @app.route('/api/stats')
    def get_stats():
        from bot import bot
        return jsonify({
            'total_servers': len(bot.guilds),
            'total_users': len(bot.users)
        })
    
    @app.errorhandler(404)
    def not_found(e):
        # Show login page with basic stats if not logged in
        from bot import bot
        total_servers = len(bot.guilds)
        total_users = len(bot.users)
        return render_template('login.html', 
                           total_servers=total_servers,
                           total_users=total_users), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_template('error.html', error=str(e)), 500
    
    return app

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('dashboard.log')
        ]
    )
    
    try:
        # Create the application
        app = create_app('development')
        
        # Always use HTTP in development
        logger.info("Starting Flask development server...")
        app.run(
            host='127.0.0.1',
            port=5001,
            debug=True,
            ssl_context=None,  # Disable SSL in development
            threaded=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask app: {e}")
        raise
