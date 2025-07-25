"""
API endpoints для работы с новеллами
"""
from flask import Blueprint, request, jsonify
from app.models import Novel
from app import db

novels_bp = Blueprint('novels', __name__)


@novels_bp.route('/novels', methods=['GET'])
def get_novels():
    """Получение списка новелл"""
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        query = Novel.query
        if active_only:
            query = query.filter_by(is_active=True)
        
        novels = query.order_by(Novel.created_at.desc()).offset(offset).limit(limit).all()
        
        novels_data = []
        for novel in novels:
            if novel and hasattr(novel, 'id') and novel.id is not None:
                novel_data = {
                    'id': novel.id,
                    'title': novel.title or 'Без названия',
                    'source_url': novel.source_url,
                    'source_type': novel.source_type or 'unknown',
                    'status': novel.status or 'unknown',
                    'total_chapters': novel.total_chapters or 0,
                    'parsed_chapters': novel.parsed_chapters or 0,
                    'translated_chapters': novel.translated_chapters or 0,
                    'edited_chapters': novel.edited_chapters or 0,
                    'is_active': novel.is_active if novel.is_active is not None else True,
                    'created_at': novel.created_at.isoformat() if novel.created_at else None,
                    'updated_at': novel.updated_at.isoformat() if novel.updated_at else None
                }
                novels_data.append(novel_data)
        
        return jsonify({
            'success': True,
            'novels': novels_data or [],
            'count': len(novels_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 