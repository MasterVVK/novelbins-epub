from flask import Blueprint

api_bp = Blueprint('api', __name__)

# Импортируем API endpoints
from .prompt_templates import prompt_templates_bp
from .glossary import glossary_bp
from .logs import logs_bp
from .tasks import tasks_bp
from .novels import novels_bp
from .console import console_bp

# Регистрируем blueprints
api_bp.register_blueprint(prompt_templates_bp, url_prefix='/prompt-templates')
api_bp.register_blueprint(glossary_bp, url_prefix='/glossary')
api_bp.register_blueprint(logs_bp, url_prefix='')
api_bp.register_blueprint(tasks_bp, url_prefix='')
api_bp.register_blueprint(novels_bp, url_prefix='')
api_bp.register_blueprint(console_bp, url_prefix='')

# Здесь будут импортироваться дополнительные API endpoints
# from .chapters import chapters_bp
# api_bp.register_blueprint(chapters_bp, url_prefix='/chapters')
