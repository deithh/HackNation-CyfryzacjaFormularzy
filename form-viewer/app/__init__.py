from flask import Flask

from app.config import Settings


def create_app() -> Flask:
    app = Flask(__name__)
    settings = Settings.from_env()
    app.config["SETTINGS"] = settings
    app.secret_key = settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_size_bytes + (256 * 1024)

    from app.routes import bp as viewer_bp
    app.register_blueprint(viewer_bp)
    return app


app = create_app()
