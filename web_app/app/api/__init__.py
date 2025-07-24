from flask import Blueprint

api_bp = Blueprint('api', __name__)

# Импортируем API endpoints
from .prompt_templates import prompt_templates_bp
from .glossary import glossary_bp

# Регистрируем blueprints
api_bp.register_blueprint(prompt_templates_bp, url_prefix='/prompt-templates')
api_bp.register_blueprint(glossary_bp, url_prefix='/glossary')

# Здесь будут импортироваться дополнительные API endpoints
# from .novels import novels_bp
# from .chapters import chapters_bp
# from .tasks import tasks_bp

# api_bp.register_blueprint(novels_bp, url_prefix='/novels')
# api_bp.register_blueprint(chapters_bp, url_prefix='/chapters')
# api_bp.register_blueprint(tasks_bp, url_prefix='/tasks')
