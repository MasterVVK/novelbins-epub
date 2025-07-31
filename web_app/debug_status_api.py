#!/usr/bin/env python3
"""
Простой API endpoint для отладки статусов.
"""

import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from flask import Flask, jsonify
from app import create_app, db
from app.models import Novel, Chapter
from app.utils.status_colors import status_colors

app = create_app('development')

@app.route('/debug/status/<int:novel_id>')
def debug_status(novel_id):
    """Отладочный endpoint для проверки статусов"""
    
    novel = Novel.query.get_or_404(novel_id)
    chapters = Chapter.query.filter_by(novel_id=novel_id).order_by(Chapter.chapter_number).all()
    
    result = {
        'novel': {
            'id': novel.id,
            'title': novel.title,
            'status': novel.status,
            'status_color': status_colors.get_novel_status_color(novel.status),
            'status_icon': status_colors.get_status_icon(novel.status, 'novel'),
            'status_text': status_colors.get_status_text(novel.status, 'novel')
        },
        'chapters': []
    }
    
    for chapter in chapters:
        chapter_data = {
            'id': chapter.id,
            'chapter_number': chapter.chapter_number,
            'status': chapter.status,
            'status_color': status_colors.get_chapter_status_color(chapter.status),
            'status_icon': status_colors.get_status_icon(chapter.status, 'chapter'),
            'status_text': status_colors.get_status_text(chapter.status, 'chapter'),
            'badge_class': f"badge bg-{status_colors.get_chapter_status_color(chapter.status)}"
        }
        result['chapters'].append(chapter_data)
    
    return jsonify(result)

@app.route('/debug/status')
def debug_all_status():
    """Отладочный endpoint для всех статусов"""
    
    novels = Novel.query.all()
    result = {
        'novels': []
    }
    
    for novel in novels:
        novel_data = {
            'id': novel.id,
            'title': novel.title,
            'status': novel.status,
            'status_color': status_colors.get_novel_status_color(novel.status)
        }
        result['novels'].append(novel_data)
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5002) 