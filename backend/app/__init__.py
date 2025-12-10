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

    # Create all database tables and run migrations on startup
    with app.app_context():
        try:
            # Import all models so SQLAlchemy knows about them
            from app.models import User, UserCredentials, WebhookLog, SymbolConfig
            
            # Create all tables defined in models (handles new tables automatically)
            db.create_all()
            app.logger.info("Database tables created/verified")
            
            # Run SQL migrations for schema changes
            from app.migrations import run_migrations
            run_migrations()
        except Exception as e:
            app.logger.error(f"Failed to initialize database: {e}")
            import traceback
            traceback.print_exc()

    # Register blueprints
    from app.routes import auth, webhooks, webhook_logs, credentials, symbol_configs
    app.register_blueprint(auth.bp)
    app.register_blueprint(webhooks.bp)
    app.register_blueprint(webhook_logs.bp)
    app.register_blueprint(credentials.bp)
    app.register_blueprint(symbol_configs.bp, url_prefix='/api/symbol-configs')

    # Register SocketIO events
    from app.services import websocket
    websocket.register_events(socketio)

    return app
