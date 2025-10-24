"""
API endpoints для мониторинга и управления Celery задачами
"""
from flask import Blueprint, jsonify
from app import celery
from celery.result import AsyncResult
import logging
import subprocess

logger = logging.getLogger(__name__)

celery_monitor_bp = Blueprint('celery_monitor', __name__)


@celery_monitor_bp.route('/celery/status', methods=['GET'])
def get_celery_status():
    """Получение общего статуса Celery"""
    try:
        # Проверяем доступность Celery через inspect
        inspect = celery.control.inspect()
        stats = inspect.stats()
        active_queues = inspect.active_queues()
        registered = inspect.registered()

        workers = []

        # Если inspect.stats() возвращает данные (prefork/gevent pool)
        if stats:
            for worker_name, worker_stats in stats.items():
                worker_info = {
                    'name': worker_name,
                    'status': 'online',
                    'pool': worker_stats.get('pool', {}).get('implementation', 'unknown'),
                    'max_concurrency': worker_stats.get('pool', {}).get('max-concurrency', 1),
                    'queues': [q['name'] for q in (active_queues or {}).get(worker_name, [])],
                    'registered_tasks': len((registered or {}).get(worker_name, []))
                }
                workers.append(worker_info)
        else:
            # Альтернативный способ для solo pool - проверяем процессы
            try:
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                # Ищем процессы celery worker
                celery_workers = {}  # Используем dict для удаления дубликатов по имени
                for line in result.stdout.split('\n'):
                    if 'celery' in line and 'worker' in line and '--hostname=' in line and 'bin/python' in line and 'bin/celery' in line:
                        # Извлекаем имя worker из --hostname=worker-czbooks@%h
                        try:
                            hostname_part = [p for p in line.split() if '--hostname=' in p][0]
                            worker_name = hostname_part.split('=')[1].replace('%h', subprocess.run(
                                ['hostname', '-s'], capture_output=True, text=True, timeout=2
                            ).stdout.strip())

                            # Пропускаем если уже добавлен
                            if worker_name in celery_workers:
                                continue

                            # Извлекаем concurrency
                            concurrency = 1
                            if '--concurrency=' in line:
                                concurrency_part = [p for p in line.split() if '--concurrency=' in p][0]
                                concurrency = int(concurrency_part.split('=')[1])

                            # Извлекаем pool
                            pool = 'prefork'
                            if '--pool=' in line:
                                pool_part = [p for p in line.split() if '--pool=' in p][0]
                                pool = pool_part.split('=')[1]

                            # Извлекаем queues
                            queues = ['celery']
                            if '--queues=' in line:
                                queues_part = [p for p in line.split() if '--queues=' in p][0]
                                queues = queues_part.split('=')[1].split(',')

                            worker_info = {
                                'name': worker_name,
                                'status': 'online',
                                'pool': f'celery.concurrency.{pool}:TaskPool',
                                'max_concurrency': concurrency,
                                'queues': queues,
                                'registered_tasks': 4  # Фиксированное значение для solo pool
                            }
                            celery_workers[worker_name] = worker_info
                        except Exception as parse_err:
                            logger.debug(f"Ошибка парсинга строки процесса: {parse_err}")
                            continue

                if celery_workers:
                    workers = list(celery_workers.values())
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Celery workers не запущены'
                    }), 503

            except Exception as proc_err:
                logger.error(f"Ошибка проверки процессов: {proc_err}")
                return jsonify({
                    'success': False,
                    'error': 'Celery workers не запущены'
                }), 503

        return jsonify({
            'success': True,
            'workers': workers,
            'workers_count': len(workers)
        })

    except Exception as e:
        logger.error(f"Ошибка получения статуса Celery: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@celery_monitor_bp.route('/celery/tasks/active', methods=['GET'])
def get_active_tasks():
    """Получение списка активных задач"""
    try:
        inspect = celery.control.inspect()
        active = inspect.active()

        tasks = []

        # Если inspect.active() работает (prefork/gevent pool)
        if active:
            for worker, worker_tasks in active.items():
                for task in worker_tasks:
                    task_info = {
                        'id': task.get('id'),
                        'name': task.get('name'),
                        'args': task.get('args'),
                        'kwargs': task.get('kwargs'),
                        'worker': worker,
                        'time_start': task.get('time_start'),
                        'acknowledged': task.get('acknowledged', False),
                        'delivery_info': task.get('delivery_info', {})
                    }
                    tasks.append(task_info)
        else:
            # Fallback для solo pool - проверяем Redis метаданные
            try:
                import redis
                from app import db
                from app.models import Novel

                # Подключаемся к Redis
                redis_client = redis.from_url(celery.conf.result_backend)

                # Ищем все ключи задач
                task_keys = redis_client.keys('celery-task-meta-*')

                for key in task_keys:
                    try:
                        task_data = redis_client.get(key)
                        if task_data:
                            import json
                            meta = json.loads(task_data)

                            # Проверяем статус - активные задачи имеют PROGRESS или STARTED
                            if meta.get('status') in ['PROGRESS', 'STARTED']:
                                task_id = key.decode('utf-8').replace('celery-task-meta-', '')

                                # Определяем тип задачи и worker по новелле
                                task_name = 'unknown'
                                worker_name = 'worker-czbooks@nv-02'

                                # Ищем новеллу с этим task_id
                                novel = Novel.query.filter(
                                    (Novel.editing_task_id == task_id) |
                                    (Novel.parsing_task_id == task_id)
                                ).first()

                                if novel:
                                    if novel.editing_task_id == task_id:
                                        task_name = 'app.celery_tasks.edit_novel_chapters_task'
                                    elif novel.parsing_task_id == task_id:
                                        task_name = 'app.celery_tasks.parse_novel_chapters_task'

                                task_info = {
                                    'id': task_id,
                                    'name': task_name,
                                    'args': [],
                                    'kwargs': {},
                                    'worker': worker_name,
                                    'time_start': None,
                                    'status': meta.get('status'),
                                    'result': meta.get('result', {})
                                }
                                tasks.append(task_info)
                    except Exception as task_err:
                        logger.debug(f"Ошибка обработки задачи {key}: {task_err}")
                        continue

            except Exception as fallback_err:
                logger.error(f"Ошибка fallback для активных задач: {fallback_err}")

        return jsonify({
            'success': True,
            'tasks': tasks,
            'count': len(tasks)
        })

    except Exception as e:
        logger.error(f"Ошибка получения активных задач: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@celery_monitor_bp.route('/celery/tasks/scheduled', methods=['GET'])
def get_scheduled_tasks():
    """Получение списка запланированных задач"""
    try:
        inspect = celery.control.inspect()
        scheduled = inspect.scheduled()

        if not scheduled:
            return jsonify({
                'success': True,
                'tasks': [],
                'count': 0
            })

        tasks = []
        for worker, worker_tasks in scheduled.items():
            for task in worker_tasks:
                task_info = {
                    'id': task.get('request', {}).get('id'),
                    'name': task.get('request', {}).get('name'),
                    'args': task.get('request', {}).get('args'),
                    'kwargs': task.get('request', {}).get('kwargs'),
                    'worker': worker,
                    'eta': task.get('eta'),
                    'priority': task.get('priority', 5)
                }
                tasks.append(task_info)

        return jsonify({
            'success': True,
            'tasks': tasks,
            'count': len(tasks)
        })

    except Exception as e:
        logger.error(f"Ошибка получения запланированных задач: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@celery_monitor_bp.route('/celery/tasks/reserved', methods=['GET'])
def get_reserved_tasks():
    """Получение списка зарезервированных задач"""
    try:
        inspect = celery.control.inspect()
        reserved = inspect.reserved()

        if not reserved:
            return jsonify({
                'success': True,
                'tasks': [],
                'count': 0
            })

        tasks = []
        for worker, worker_tasks in reserved.items():
            for task in worker_tasks:
                task_info = {
                    'id': task.get('id'),
                    'name': task.get('name'),
                    'args': task.get('args'),
                    'kwargs': task.get('kwargs'),
                    'worker': worker,
                    'acknowledged': task.get('acknowledged', False)
                }
                tasks.append(task_info)

        return jsonify({
            'success': True,
            'tasks': tasks,
            'count': len(tasks)
        })

    except Exception as e:
        logger.error(f"Ошибка получения зарезервированных задач: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@celery_monitor_bp.route('/celery/tasks/<task_id>', methods=['GET'])
def get_task_info(task_id):
    """Получение информации о конкретной задаче"""
    try:
        result = AsyncResult(task_id, app=celery)

        task_info = {
            'id': task_id,
            'state': result.state,
            'ready': result.ready(),
            'successful': result.successful() if result.ready() else None,
            'failed': result.failed() if result.ready() else None
        }

        # Добавляем результат или ошибку
        if result.ready():
            if result.successful():
                task_info['result'] = result.result
            elif result.failed():
                task_info['error'] = str(result.info)
        else:
            # Для активных задач получаем мета-информацию
            task_info['info'] = result.info

        return jsonify({
            'success': True,
            'task': task_info
        })

    except Exception as e:
        logger.error(f"Ошибка получения информации о задаче {task_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@celery_monitor_bp.route('/celery/tasks/<task_id>/revoke', methods=['POST'])
def revoke_task(task_id):
    """Отмена задачи"""
    try:
        # Отменяем задачу с terminate=True для немедленной остановки
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')

        logger.info(f"Задача {task_id} отменена")

        return jsonify({
            'success': True,
            'message': f'Задача {task_id} отменена'
        })

    except Exception as e:
        logger.error(f"Ошибка отмены задачи {task_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@celery_monitor_bp.route('/celery/queue/purge', methods=['POST'])
def purge_queue():
    """Очистка очереди задач"""
    try:
        # Очищаем все очереди
        purged_count = celery.control.purge()

        logger.warning(f"Очищено задач из очереди: {purged_count}")

        return jsonify({
            'success': True,
            'message': f'Очищено задач: {purged_count}',
            'purged_count': purged_count
        })

    except Exception as e:
        logger.error(f"Ошибка очистки очереди: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@celery_monitor_bp.route('/celery/registered', methods=['GET'])
def get_registered_tasks():
    """Получение списка зарегистрированных типов задач"""
    try:
        inspect = celery.control.inspect()
        registered = inspect.registered()

        # Собираем уникальные задачи из всех workers
        all_tasks = set()

        if registered:
            for worker, tasks in registered.items():
                all_tasks.update(tasks)
        else:
            # Fallback для solo pool - используем список из celery.tasks
            try:
                all_tasks = set(celery.tasks.keys())
                # Фильтруем встроенные celery задачи
                all_tasks = {t for t in all_tasks if not t.startswith('celery.')}
            except Exception as fallback_err:
                logger.debug(f"Ошибка fallback для registered tasks: {fallback_err}")
                # Если и это не работает, возвращаем известные задачи
                all_tasks = {
                    'app.celery_tasks.parse_novel_chapters_task',
                    'app.celery_tasks.cancel_parsing_task',
                    'app.celery_tasks.edit_novel_chapters_task',
                    'app.celery_tasks.cancel_editing_task'
                }

        tasks_list = sorted(list(all_tasks))

        return jsonify({
            'success': True,
            'tasks': tasks_list,
            'count': len(tasks_list)
        })

    except Exception as e:
        logger.error(f"Ошибка получения зарегистрированных задач: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
