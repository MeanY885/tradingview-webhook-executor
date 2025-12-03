"""Flask application factory."""
from flask import Flask
from flask_cors import CORS
from app.extensions import db, jwt, socketio
from app.config import Config


def create_app(config_class=Config):
    """Create and configure Flask application with SocketIO support."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    # CORS for REST API
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config['FRONTEND_URL'],
            "supports_credentials": True
        }
    })

    # Run database migrations on startup
    with app.app_context():
        try:
            from app.migrations import run_migrations
            run_migrations()
        except Exception as e:
            app.logger.error(f"Failed to run migrations: {e}")
            # Don't crash the app, but log the error
            # Migrations might fail if database isn't ready yet

    # Register blueprints
    from app.routes import auth, webhooks, webhook_logs, credentials
    app.register_blueprint(auth.bp)
    app.register_blueprint(webhooks.bp)
    app.register_blueprint(webhook_logs.bp)
    app.register_blueprint(credentials.bp)

    # Register SocketIO events
    from app.services import websocket
    websocket.register_events(socketio)

    return app
