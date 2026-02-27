"""Code Logger Backend API."""
from flask import Flask
from flask_cors import CORS
from app.config import Config
from app.api.routes import register_routes


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    register_routes(app)
    return app


app = create_app()
