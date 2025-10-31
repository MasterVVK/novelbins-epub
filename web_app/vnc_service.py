#!/usr/bin/env python3
"""
VNC Service для трансляции Selenium браузера в веб-интерфейс

Управляет:
- x11vnc сервером на Xvfb дисплее
- websockify прокси для noVNC
"""

import os
import sys
import subprocess
import signal
import time
import psutil
from pathlib import Path

class VNCService:
    def __init__(self, display=":99", vnc_port=5900, websocket_port=6080):
        self.display = display
        self.vnc_port = vnc_port
        self.websocket_port = websocket_port
        self.x11vnc_process = None
        self.websockify_process = None

        # Пути для PID файлов
        self.pid_dir = Path("/tmp/novelbins_vnc")
        self.pid_dir.mkdir(exist_ok=True)
        self.x11vnc_pidfile = self.pid_dir / "x11vnc.pid"
        self.websockify_pidfile = self.pid_dir / "websockify.pid"

    def is_running(self, pidfile):
        """Проверить, запущен ли процесс"""
        if not pidfile.exists():
            return False

        try:
            with open(pidfile) as f:
                pid = int(f.read().strip())

            # Проверяем, существует ли процесс
            return psutil.pid_exists(pid)
        except:
            return False

    def start_x11vnc(self):
        """Запустить x11vnc сервер"""
        if self.is_running(self.x11vnc_pidfile):
            print(f"✅ x11vnc уже запущен на {self.display}")
            return True

        print(f"🚀 Запуск x11vnc на дисплее {self.display}...")

        cmd = [
            'x11vnc',
            '-display', self.display,
            '-rfbport', str(self.vnc_port),
            '-shared',  # Разрешить множественные подключения
            '-forever',  # Не завершаться после отключения клиента
            '-nopw',  # Без пароля (защищено на уровне сети)
            '-quiet',
            '-bg',  # Фоновый режим
            '-o', '/tmp/x11vnc.log',
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            # x11vnc в -bg режиме выводит PID в stderr
            time.sleep(1)

            # Найдем PID процесса
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'x11vnc' and self.display in proc.info['cmdline']:
                        pid = proc.info['pid']
                        with open(self.x11vnc_pidfile, 'w') as f:
                            f.write(str(pid))
                        print(f"✅ x11vnc запущен (PID: {pid})")
                        return True
                except:
                    continue

            print(f"⚠️ x11vnc запущен, но PID не найден")
            return True

        except Exception as e:
            print(f"❌ Ошибка запуска x11vnc: {e}")
            return False

    def start_websockify(self):
        """Запустить websockify прокси"""
        if self.is_running(self.websockify_pidfile):
            print(f"✅ websockify уже запущен на порту {self.websocket_port}")
            return True

        print(f"🚀 Запуск websockify на порту {self.websocket_port}...")

        # Путь к noVNC
        novnc_path = Path(__file__).parent / 'app' / 'static' / 'novnc'

        cmd = [
            sys.executable, '-m', 'websockify',
            '--web', str(novnc_path),
            str(self.websocket_port),
            f'localhost:{self.vnc_port}',
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )

            # Сохраняем PID
            with open(self.websockify_pidfile, 'w') as f:
                f.write(str(process.pid))

            # Проверяем, что процесс запустился
            time.sleep(1)
            if process.poll() is None:
                print(f"✅ websockify запущен (PID: {process.pid})")
                return True
            else:
                print(f"❌ websockify завершился с кодом {process.returncode}")
                return False

        except Exception as e:
            print(f"❌ Ошибка запуска websockify: {e}")
            return False

    def stop_process(self, pidfile, name):
        """Остановить процесс по PID файлу"""
        if not pidfile.exists():
            print(f"⚠️ {name} не запущен")
            return True

        try:
            with open(pidfile) as f:
                pid = int(f.read().strip())

            if not psutil.pid_exists(pid):
                print(f"⚠️ {name} процесс не найден")
                pidfile.unlink()
                return True

            print(f"🛑 Остановка {name} (PID: {pid})...")
            os.kill(pid, signal.SIGTERM)

            # Ждем завершения
            for _ in range(10):
                if not psutil.pid_exists(pid):
                    pidfile.unlink()
                    print(f"✅ {name} остановлен")
                    return True
                time.sleep(0.5)

            # Принудительное завершение
            print(f"⚠️ {name} не остановился, отправка SIGKILL...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
            pidfile.unlink()
            print(f"✅ {name} принудительно остановлен")
            return True

        except Exception as e:
            print(f"❌ Ошибка остановки {name}: {e}")
            return False

    def start(self):
        """Запустить VNC сервис"""
        print("=" * 60)
        print("VNC Service - Запуск")
        print("=" * 60)

        success = True
        success &= self.start_x11vnc()
        success &= self.start_websockify()

        if success:
            print()
            print("✅ VNC сервис успешно запущен!")
            print(f"📺 VNC порт: {self.vnc_port}")
            print(f"🌐 WebSocket порт: {self.websocket_port}")
            print(f"🔗 noVNC URL: http://localhost:{self.websocket_port}/vnc.html")
        else:
            print()
            print("❌ Ошибка запуска VNC сервиса")

        return success

    def stop(self):
        """Остановить VNC сервис"""
        print("=" * 60)
        print("VNC Service - Остановка")
        print("=" * 60)

        self.stop_process(self.websockify_pidfile, "websockify")
        self.stop_process(self.x11vnc_pidfile, "x11vnc")

        print()
        print("✅ VNC сервис остановлен")

    def status(self):
        """Показать статус VNC сервиса"""
        print("=" * 60)
        print("VNC Service - Статус")
        print("=" * 60)

        x11vnc_running = self.is_running(self.x11vnc_pidfile)
        websockify_running = self.is_running(self.websockify_pidfile)

        print(f"x11vnc: {'✅ Запущен' if x11vnc_running else '❌ Остановлен'}")
        print(f"websockify: {'✅ Запущен' if websockify_running else '❌ Остановлен'}")

        if x11vnc_running and websockify_running:
            print()
            print(f"🔗 VNC доступен: http://localhost:{self.websocket_port}/vnc.html")

        return x11vnc_running and websockify_running

def main():
    """CLI интерфейс"""
    service = VNCService()

    if len(sys.argv) < 2:
        print("Использование: python vnc_service.py {start|stop|restart|status}")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'start':
        service.start()
    elif command == 'stop':
        service.stop()
    elif command == 'restart':
        service.stop()
        time.sleep(1)
        service.start()
    elif command == 'status':
        service.status()
    else:
        print(f"❌ Неизвестная команда: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()
