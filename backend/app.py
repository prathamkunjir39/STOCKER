"""
Flask Application Factory
Creates and configures the Flask application
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import get_config
from database import engine, init_db, check_db_connection, close_db_session, get_db_session
from auth_service import get_current_user

logger = logging.getLogger(__name__)


def create_app(config_object=None) -> Flask:
    """
    Application factory pattern

    Args:
        config_object: Config class to use (defaults to FLASK_ENV)

    Returns:
        Configured Flask application
    """
    # ============= CREATE APP =============
    app = Flask(__name__)

    # ============= LOAD CONFIG =============
    if config_object is None:
        config_object = get_config()

    app.config.from_object(config_object)
    logger.info(f"Loaded configuration: {config_object.__name__}")

    # ============= SETUP LOGGING =============
    setup_logging(app)

    # ============= DATABASE TEARDOWN =============
    def cleanup_db_session(error):
        """Remove scoped session at end of request"""
        from database import db_session
        db_session.remove()

    app.teardown_appcontext(cleanup_db_session)

    # ============= RATE LIMITING =============
    if app.config.get("RATELIMIT_ENABLED") and not app.config.get("TESTING"):
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=[app.config.get("RATELIMIT_DEFAULT", "100/hour")],
            storage_uri=app.config.get("RATELIMIT_STORAGE_URL", "memory://"),
            headers_enabled=True,
            swallow_errors=True,
            meta_limits=[],
        )

        @limiter.request_filter
        def _skip_rate_limit():
            if request.path == "/health":
                return True
            return False

        app.extensions["limiter"] = limiter
        logger.info(
            "Rate limiting enabled: %s (storage %s)",
            app.config.get("RATELIMIT_DEFAULT"),
            app.config.get("RATELIMIT_STORAGE_URL", "memory://"),
        )
    else:
        logger.info("Rate limiting disabled for this configuration")

    # ============= CORS CONFIGURATION =============
    cors_origins = app.config.get('CORS_ORIGINS', ['http://localhost:5173'])
    CORS(app,
         origins=cors_origins,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         max_age=3600,
         supports_credentials=True)

    logger.info(f"CORS configured for origins: {cors_origins}")

    # ============= REQUEST ID MIDDLEWARE =============
    @app.before_request
    def assign_request_id():
        """Assign unique request ID for tracing"""
        import uuid
        g.request_id = str(uuid.uuid4())

    # ============= REQUEST TIMING MIDDLEWARE =============
    @app.before_request
    def start_timer():
        """Start request timer"""
        import time
        g.start_time = time.time()

    @app.after_request
    def log_response(response):
        """Log request completion with timing"""
        import time
        if hasattr(g, 'start_time'):
            elapsed = time.time() - g.start_time
            logger.info(
                f"[{g.get('request_id', 'unknown')}] "
                f"{request.method} {request.path} - "
                f"{response.status_code} - {elapsed:.2f}s"
            )
        return response

    # ============= ERROR HANDLERS =============
    register_error_handlers(app)

    # ============= REGISTER BLUEPRINTS =============
    register_blueprints(app)
    _apply_route_rate_limits(app)

    # ============= HEALTH CHECK =============
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for monitoring"""
        from datetime import datetime
        from sqlalchemy import text

        try:
            # Test database connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            db_status = "OK"
        except Exception as e:
            logger.error(f"Health check DB error: {str(e)}")
            db_status = "ERROR"

        return {
            "status": "healthy" if db_status == "OK" else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_status,
            "version": "2.0"
        }, 200 if db_status == "OK" else 503

    # ============= APP STARTUP LOG =============
    logger.info("=" * 60)
    logger.info("Stocker Enterprise API Server Initialized")
    logger.info(f"Environment: {config_object.__name__}")
    logger.info(f"Debug: {app.config.get('DEBUG', False)}")
    logger.info(f"Database: {config_object.DATABASE_URL.split('@')[-1] if '@' in config_object.DATABASE_URL else config_object.DATABASE_URL}")
    logger.info("=" * 60)

    return app


def setup_logging(app: Flask):
    """Configure logging for the application"""
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper())

    # Ensure logs directory exists
    log_file = app.config.get('LOG_FILE', 'logs/app.log')
    os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {log_level} level")
    logger.info(f"Log file: {log_file}")


def register_error_handlers(app: Flask):
    """Register global error handlers"""

    @app.errorhandler(404)
    def not_found(error):
        logger.warning(f"404: {request.path}")
        return {
            "status": "error",
            "error": "Endpoint not found",
            "code": "NOT_FOUND",
            "path": request.path
        }, 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        logger.warning(f"405: {request.method} {request.path}")
        return {
            "status": "error",
            "error": "Method not allowed",
            "code": "METHOD_NOT_ALLOWED"
        }, 405

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500: {str(error)}", exc_info=True)
        return {
            "status": "error",
            "error": "Internal server error",
            "code": "INTERNAL_ERROR"
        }, 500

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        logger.warning(f"429: Rate limit exceeded - {request.path}")
        return {
            "status": "error",
            "error": "Rate limit exceeded",
            "code": "RATE_LIMIT_EXCEEDED"
        }, 429


def register_blueprints(app: Flask):
    """Register Flask blueprints for modular routing"""
    from routes.auth import auth_bp
    from routes.forecast import forecast_bp
    from routes.inventory import inventory_bp
    from routes.analytics import analytics_bp
    from routes.planning import planning_bp
    from routes.procurement import procurement_bp
    from routes.anomaly import anomaly_bp
    from routes.recommendation import recommendation_bp
    from routes.report import report_bp
    from routes.chatbot import chatbot_bp

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(forecast_bp, url_prefix='/api/forecast')
    app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(planning_bp, url_prefix='/api/planning')
    app.register_blueprint(procurement_bp, url_prefix='/api/procurement')
    app.register_blueprint(anomaly_bp, url_prefix='/api/anomalies')
    app.register_blueprint(recommendation_bp, url_prefix='/api/recommendations')
    app.register_blueprint(report_bp, url_prefix='/api/reports')
    app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')

    logger.info("All blueprints registered")


def _apply_route_rate_limits(app: Flask) -> None:
    """Tight limits on auth endpoints (global limiter still applies when enabled)."""
    limiter = app.extensions.get("limiter")
    if not limiter:
        return
    auth = app.blueprints.get("auth")
    if not auth:
        return
    vf = auth.view_functions
    if "login" in vf:
        limiter.limit("10 per minute")(vf["login"])
    if "register" in vf:
        limiter.limit("5 per minute")(vf["register"])
    if "refresh_token" in vf:
        limiter.limit("30 per minute")(vf["refresh_token"])
    logger.info("Auth route rate limits attached (login/register/refresh)")
