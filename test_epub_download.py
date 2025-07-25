#!/usr/bin/env python3
"""
Тест скачивания EPUB
"""
import requests
import sys
import os
from pathlib import Path

# Добавляем путь к web_app
web_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app')
sys.path.insert(0, web_app_path)

from app import create_app, db
from app.models import Novel, Task

def test_epub_download():
    """Тестирование скачивания EPUB"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Тестирование скачивания EPUB...")
        
        # Получаем первую новеллу
        novel = Novel.query.first()
        if not novel:
            print("❌ Нет новелл в базе данных")
            return
        
        print(f"📖 Найдена новелла: {novel.title} (ID: {novel.id})")
        
        # Проверяем завершенную задачу EPUB
        completed_epub_task = Task.query.filter_by(
            novel_id=novel.id,
            task_type='generate_epub',
            status='completed'
        ).order_by(Task.updated_at.desc()).first()
        
        if not completed_epub_task:
            print("❌ Нет завершенной задачи EPUB")
            return
        
        print(f"✅ Найдена завершенная задача EPUB: {completed_epub_task.id}")
        
        if not completed_epub_task.result or 'epub_path' not in completed_epub_task.result:
            print("❌ Нет пути к EPUB файлу в результате")
            return
        
        epub_path = completed_epub_task.result['epub_path']
        epub_file = Path(epub_path)
        
        if not epub_file.exists():
            print(f"❌ EPUB файл не найден: {epub_path}")
            return
        
        size_kb = epub_file.stat().st_size / 1024
        print(f"✅ EPUB файл найден: {epub_path}")
        print(f"📊 Размер: {size_kb:.1f} KB")
        
        # Тестируем скачивание через веб-интерфейс
        base_url = "http://localhost:5001"
        download_url = f"{base_url}/novels/{novel.id}/epub/download"
        
        print(f"\n🔗 URL для скачивания: {download_url}")
        
        try:
            response = requests.get(download_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ Скачивание успешно!")
                print(f"📊 Размер ответа: {len(response.content)} байт")
                print(f"📋 Content-Type: {response.headers.get('content-type', 'не указан')}")
                print(f"📋 Content-Disposition: {response.headers.get('content-disposition', 'не указан')}")
                
                # Сохраняем тестовый файл
                test_file = Path("test_download.epub")
                with open(test_file, 'wb') as f:
                    f.write(response.content)
                
                test_size_kb = test_file.stat().st_size / 1024
                print(f"✅ Тестовый файл сохранен: {test_file}")
                print(f"📊 Размер тестового файла: {test_size_kb:.1f} KB")
                
                # Удаляем тестовый файл
                test_file.unlink()
                print("🗑️ Тестовый файл удален")
                
            else:
                print(f"❌ Ошибка скачивания: {response.status_code}")
                print(f"📋 Ответ: {response.text[:200]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса: {e}")
            print("💡 Убедитесь, что веб-приложение запущено на http://localhost:5001")

if __name__ == "__main__":
    test_epub_download() 