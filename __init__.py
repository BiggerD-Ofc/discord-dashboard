"""
Dashboard package for the Discord bot.

This package contains the web dashboard for managing the bot.
"""

# Import app module without creating circular imports
__all__ = ['create_app']

# This is a placeholder - the actual import is done in the create_app function
def create_app(env='development'):
    """Create and configure the Flask application."""
    from .app import create_app as _create_app
    return _create_app(env)
