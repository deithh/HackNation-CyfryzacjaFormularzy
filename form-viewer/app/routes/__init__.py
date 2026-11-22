from flask import Blueprint

from app.routes import pages, uploads

bp = Blueprint("viewer", __name__)

bp.add_url_rule("/", view_func=pages.index, methods=["GET"])
bp.add_url_rule("/form", view_func=pages.preview_form, methods=["GET"])
bp.add_url_rule("/json", view_func=pages.view_json, methods=["GET"])
bp.add_url_rule("/download-json", view_func=pages.download_json, methods=["GET"])
bp.add_url_rule("/upload-form", view_func=uploads.upload_form, methods=["POST"])
bp.add_url_rule("/upload-json", view_func=uploads.upload_json, methods=["POST"])
