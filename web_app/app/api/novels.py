"""
API endpoints для работы с новеллами
"""
from flask import Blueprint, request, jsonify, render_template_string
from app.models import Novel
from app import db
import re

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


@novels_bp.route('/cloudflare-auth/window', methods=['GET'])
def cloudflare_auth_window():
    """
    Возвращает HTML страницу для прохождения Cloudflare challenge
    Используется в popup окне или iframe
    """
    target_url = request.args.get('url', 'https://czbooks.net')

    # HTML template для Cloudflare auth окна
    html_template = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cloudflare Authentication</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            padding: 20px;
            background: #f8f9fa;
        }
        .auth-container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .status-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        #iframe-container {
            position: relative;
            width: 100%;
            height: 600px;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            overflow: hidden;
            background: white;
        }
        #target-frame {
            width: 100%;
            height: 100%;
            border: none;
        }
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255,255,255,0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-checking { background: #ffc107; }
        .status-success { background: #28a745; }
        .status-error { background: #dc3545; }
        .cookie-preview {
            max-height: 150px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            word-break: break-all;
        }
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="status-card">
            <h4><i class="bi bi-shield-check"></i> Cloudflare Authentication</h4>
            <p class="mb-2">Пожалуйста, дождитесь прохождения проверки Cloudflare...</p>
            <div class="d-flex align-items-center">
                <span id="status-indicator" class="status-indicator status-checking"></span>
                <strong id="status-text">Проверка безопасности...</strong>
            </div>
            <div class="progress mt-3" style="height: 4px;">
                <div id="progress-bar" class="progress-bar progress-bar-striped progress-bar-animated"
                     role="progressbar" style="width: 0%"></div>
            </div>
        </div>

        <div id="cookies-card" class="status-card" style="display: none;">
            <h5><i class="bi bi-cookie"></i> Полученные Cookies</h5>
            <div id="cookie-preview" class="cookie-preview"></div>
            <button id="copy-cookies-btn" class="btn btn-sm btn-outline-primary mt-2">
                <i class="bi bi-clipboard"></i> Скопировать
            </button>
        </div>

        <div id="iframe-container">
            <div id="loading-overlay" class="loading-overlay">
                <div class="text-center">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Загрузка...</span>
                    </div>
                    <p class="mt-3">Загрузка страницы...</p>
                </div>
            </div>
            <iframe id="target-frame" src="{{ target_url }}" sandbox="allow-same-origin allow-scripts allow-forms"></iframe>
        </div>

        <div class="status-card mt-3">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <small class="text-muted">
                        <i class="bi bi-info-circle"></i>
                        Cookies будут автоматически извлечены после прохождения проверки
                    </small>
                </div>
                <div>
                    <button id="close-btn" class="btn btn-secondary btn-sm" style="display: none;">
                        <i class="bi bi-x-lg"></i> Закрыть
                    </button>
                    <button id="done-btn" class="btn btn-success btn-sm" style="display: none;" disabled>
                        <i class="bi bi-check-lg"></i> Готово
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
    (function() {
        const iframe = document.getElementById('target-frame');
        const loadingOverlay = document.getElementById('loading-overlay');
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        const progressBar = document.getElementById('progress-bar');
        const cookiesCard = document.getElementById('cookies-card');
        const cookiePreview = document.getElementById('cookie-preview');
        const copyBtn = document.getElementById('copy-cookies-btn');
        const closeBtn = document.getElementById('close-btn');
        const doneBtn = document.getElementById('done-btn');

        let checkInterval = null;
        let progress = 0;
        let extractedCookies = '';

        // Скрываем loading overlay после загрузки iframe
        iframe.addEventListener('load', function() {
            setTimeout(() => {
                loadingOverlay.style.display = 'none';
            }, 500);

            // Начинаем проверку cookies
            startCookieCheck();
        });

        function startCookieCheck() {
            checkInterval = setInterval(checkForCloudflareSuccess, 2000);

            // Анимация прогресс-бара
            const progressInterval = setInterval(() => {
                progress += 2;
                if (progress >= 90) progress = 90; // Останавливаемся на 90%
                progressBar.style.width = progress + '%';

                if (extractedCookies) {
                    clearInterval(progressInterval);
                    progressBar.style.width = '100%';
                }
            }, 200);
        }

        async function checkForCloudflareSuccess() {
            try {
                // Пытаемся получить cookies через различные методы
                let cookies = '';

                // Метод 1: document.cookie (работает если same-origin)
                try {
                    cookies = iframe.contentWindow.document.cookie;
                } catch (e) {
                    // Same-origin policy - ожидаемо для cross-origin iframe
                    console.log('Cross-origin iframe, используем альтернативные методы');
                }

                // Метод 2: Используем postMessage для получения cookies из iframe
                if (!cookies) {
                    iframe.contentWindow.postMessage({
                        action: 'getCookies'
                    }, '{{ target_url }}');
                }

                // Проверяем наличие Cloudflare cookies
                if (cookies && (cookies.includes('cf_clearance') || cookies.includes('__cf_bm'))) {
                    onCloudflareSuccess(cookies);
                }

            } catch (error) {
                console.error('Ошибка проверки cookies:', error);
            }
        }

        function onCloudflareSuccess(cookies) {
            clearInterval(checkInterval);
            extractedCookies = cookies;

            // Обновляем UI
            statusIndicator.className = 'status-indicator status-success';
            statusText.textContent = '✅ Проверка пройдена!';
            progressBar.style.width = '100%';
            progressBar.classList.remove('progress-bar-animated');

            // Показываем cookies
            cookiesCard.style.display = 'block';
            cookiePreview.textContent = cookies || 'Cookies получены';

            // Активируем кнопки
            closeBtn.style.display = 'inline-block';
            doneBtn.style.display = 'inline-block';
            doneBtn.disabled = false;

            // Отправляем cookies в parent window
            if (window.opener) {
                window.opener.postMessage({
                    action: 'cloudflareSuccess',
                    cookies: cookies,
                    url: '{{ target_url }}'
                }, '*');
            }

            // Или через iframe parent
            if (window.parent !== window) {
                window.parent.postMessage({
                    action: 'cloudflareSuccess',
                    cookies: cookies,
                    url: '{{ target_url }}'
                }, '*');
            }
        }

        // Обработчик для получения cookies из iframe через postMessage
        window.addEventListener('message', function(event) {
            if (event.data && event.data.action === 'cookiesResponse') {
                if (event.data.cookies) {
                    onCloudflareSuccess(event.data.cookies);
                }
            }
        });

        // Копирование cookies
        copyBtn.addEventListener('click', function() {
            navigator.clipboard.writeText(extractedCookies).then(() => {
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="bi bi-check"></i> Скопировано!';
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                }, 2000);
            });
        });

        // Закрытие окна
        closeBtn.addEventListener('click', function() {
            window.close();
        });

        doneBtn.addEventListener('click', function() {
            // Отправляем финальное подтверждение
            if (window.opener) {
                window.opener.postMessage({
                    action: 'cloudflareComplete',
                    cookies: extractedCookies,
                    url: '{{ target_url }}'
                }, '*');
            }
            if (window.parent !== window) {
                window.parent.postMessage({
                    action: 'cloudflareComplete',
                    cookies: extractedCookies,
                    url: '{{ target_url }}'
                }, '*');
            }
            window.close();
        });
    })();
    </script>
</body>
</html>
    '''

    return render_template_string(html_template, target_url=target_url)


@novels_bp.route('/cloudflare-auth/save-cookies', methods=['POST'])
def save_cloudflare_cookies():
    """
    Сохраняет полученные Cloudflare cookies для новеллы
    """
    try:
        data = request.get_json()

        novel_id = data.get('novel_id')
        cookies = data.get('cookies')
        source_url = data.get('source_url')

        if not cookies:
            return jsonify({
                'success': False,
                'error': 'Cookies не предоставлены'
            }), 400

        # Если указан novel_id, обновляем существующую новеллу
        if novel_id:
            novel = Novel.query.get(novel_id)
            if not novel:
                return jsonify({
                    'success': False,
                    'error': 'Новелла не найдена'
                }), 404

            novel.auth_cookies = cookies
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Cookies успешно сохранены',
                'novel_id': novel_id
            })

        # Иначе просто возвращаем cookies для использования при создании
        return jsonify({
            'success': True,
            'cookies': cookies,
            'message': 'Cookies получены, используйте их при создании новеллы'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@novels_bp.route('/cloudflare-auth/check-cookies', methods=['POST'])
def check_cloudflare_cookies():
    """
    Проверяет валидность Cloudflare cookies
    """
    try:
        data = request.get_json()
        cookies = data.get('cookies', '')

        # Проверяем наличие основных Cloudflare cookies
        has_clearance = 'cf_clearance' in cookies
        has_bm = '__cf_bm' in cookies
        has_cfuvid = '_cfuvid' in cookies

        is_valid = has_clearance or (has_bm and has_cfuvid)

        # Извлекаем домен
        domain_match = re.search(r'domain=([^;]+)', cookies)
        domain = domain_match.group(1) if domain_match else 'unknown'

        return jsonify({
            'success': True,
            'valid': is_valid,
            'has_cf_clearance': has_clearance,
            'has_cf_bm': has_bm,
            'has_cfuvid': has_cfuvid,
            'domain': domain,
            'cookies_count': len(cookies.split(';'))
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@novels_bp.route('/extension/version', methods=['GET'])
def get_extension_version():
    """
    Возвращает текущую версию Browser Extension
    """
    try:
        return jsonify({
            'success': True,
            'version': '1.1.0',
            'changelog': [
                'Исправлена ошибка chrome.storage.sync',
                'Увеличено время ожидания до 15 секунд',
                'Автоматическое открытие конкретной страницы новеллы',
                'Улучшенные сообщения об ошибках'
            ],
            'download_url': '/download-extension'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@novels_bp.route('/novels/<int:novel_id>/status', methods=['GET'])
def get_novel_status(novel_id):
    """
    Получение текущего статуса новеллы для real-time polling
    Используется для обновления UI без перезагрузки страницы
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        # Проверяем наличие активных задач
        has_active_tasks = bool(
            novel.parsing_task_id or
            novel.editing_task_id or
            novel.alignment_task_id or
            novel.epub_generation_task_id
        )

        # Формируем ответ с полной информацией о статусе
        response = {
            'success': True,
            'novel_id': novel.id,
            'status': novel.status or 'unknown',
            'has_active_tasks': has_active_tasks,

            # Активные задачи
            'tasks': {
                'parsing': novel.parsing_task_id,
                'editing': novel.editing_task_id,
                'alignment': novel.alignment_task_id,
                'epub_generation': novel.epub_generation_task_id
            },

            # Прогресс
            'progress': {
                'total_chapters': novel.total_chapters or 0,
                'parsed_chapters': novel.parsed_chapters or 0,
                'translated_chapters': novel.translated_chapters or 0,
                'edited_chapters': novel.edited_chapters or 0,
                'aligned_chapters': novel.aligned_chapters or 0,

                # Проценты
                'parsing_percentage': novel.parsing_progress_percentage,
                'translation_percentage': novel.progress_percentage,
                'editing_percentage': novel.editing_progress_percentage,
                'alignment_percentage': novel.alignment_progress_percentage
            },

            # Дополнительная информация
            'epub_path': novel.epub_path,
            'updated_at': novel.updated_at.isoformat() if novel.updated_at else None
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 