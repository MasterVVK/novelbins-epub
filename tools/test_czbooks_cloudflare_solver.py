#!/usr/bin/env python3
"""
Тестовый скрипт для эмуляции прохождения Cloudflare Turnstile на czbooks.net.
Запускает тот же стек, что и парсер проекта: undetected-chromedriver + solver Qwen3-VL.

Как использовать:
  python tools/test_czbooks_cloudflare_solver.py \
    --url https://czbooks.net \
    --headless false \
    --proxy socks5://user:pass@host:port \
    --max-attempts 3

В выводе видно:
  - инициализацию драйвера и VNC
  - детекцию Cloudflare
  - работу solver'а (скриншот, координаты, клики)
  - длину загруженной страницы и количество китайских символов
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import parsers.sources.czbooks_parser as cz  # noqa: E402
from parsers.sources.czbooks_parser import CZBooksParser  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke-тест обхода Cloudflare для czbooks.net")
    parser.add_argument("--url", default="https://czbooks.net", help="Страница, которую грузим (по умолчанию главная)")
    parser.add_argument("--headless", default="false", choices=["true", "false"], help="Headless режим браузера")
    parser.add_argument("--proxy", help="SOCKS5 прокси, например socks5://user:pass@host:port")
    parser.add_argument("--cookies", help="Строка cookies для авторизации")
    parser.add_argument("--max-attempts", type=int, default=3, help="Попытки прохода Cloudflare")
    parser.add_argument("--no-fallback", action="store_true", help="Не переключаться на обычный Selenium при ошибке undetected")
    return parser.parse_args()


def run_once(args, headless: bool) -> str:
    # Монки-патч _init_selenium, чтобы не падать на повторном использовании options
    # и избегать версии с жестким version_main. Используется ТОЛЬКО в тестовом скрипте.
    def patched_init_selenium(self):  # noqa: D401
        if self.driver:
            return

        import undetected_chromedriver as uc  # noqa: WPS433

        def build_options():
            opts = uc.ChromeOptions()
            if self.headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            if not self.headless:
                opts.add_argument("--start-maximized")
            if self.socks_proxy:
                proxy_url = self.socks_proxy.replace("socks5://", "")
                opts.add_argument(f"--proxy-server=socks5://{proxy_url}")
            return opts

        # Определяем мажорную версию Chrome для точного совпадения с драйвером
        import subprocess
        version_main = None
        try:
            chrome_path = uc.find_chrome_executable()
            result = subprocess.run(
                [chrome_path, '--version'],
                capture_output=True, text=True, timeout=5
            )
            import re as _re
            version_match = _re.search(r'(\d+)\.', result.stdout)
            version_main = int(version_match.group(1)) if version_match else None
        except Exception:
            pass

        # Две попытки с новыми options
        last_err = None
        for idx in range(2):
            try:
                opts = build_options()
                self.driver = uc.Chrome(options=opts, version_main=version_main)
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue

        if not self.driver:
            raise last_err or RuntimeError("Не удалось инициализировать undetected-chromedriver")

        self.driver.set_page_load_timeout(300)
        self.driver.set_script_timeout(60)
        self._start_vnc_if_needed()

        if self.auth_cookies and self.auth_cookies.strip():
            try:
                self.driver.set_page_load_timeout(30)
                self.driver.get(self.base_url)
            except Exception:
                try:
                    self.driver.execute_script("window.stop();")
                except Exception:
                    pass
            self.driver.set_page_load_timeout(300)

    cz.CZBooksParser._init_selenium = patched_init_selenium  # type: ignore[assignment]

    parser = CZBooksParser(
        auth_cookies=args.cookies,
        socks_proxy=args.proxy,
        headless=headless,
        cloudflare_max_attempts=args.max_attempts,
    )

    try:
        return parser._get_page_with_selenium(  # pylint: disable=protected-access
            args.url,
            wait_selector="body",
            wait_time=20,
        )
    finally:
        parser.close()


def main():
    args = parse_args()

    headless = args.headless.lower() == "true"

    print("=" * 80)
    print("🚦 Cloudflare Turnstile smoke-test для czbooks.net")
    print(f"URL:          {args.url}")
    print(f"Headless:     {headless}")
    print(f"Proxy:        {args.proxy or '-'}")
    print(f"Max attempts: {args.max_attempts}")
    print("=" * 80)

    try:
        html = run_once(args, headless=headless)
        chinese_chars = len([c for c in html if "\u4e00" <= c <= "\u9fff"])
        print("-" * 80)
        print(f"✅ Страница загружена: {len(html)} символов, китайских: {chinese_chars}")
        print("-" * 80)
        return
    except Exception as exc:  # noqa: BLE001
        print("-" * 80)
        print(f"⚠️ Первая попытка неудачна: {exc}")
        print("Пробуем fallback на обычный Selenium (use_undetected=False)...")
        print("-" * 80)

        # Форсим fallback на обычный Selenium, если он доступен
        cz.use_undetected = False
        try:
            from selenium import webdriver as selenium_webdriver  # noqa: WPS433
            from selenium.webdriver.chrome.options import Options as SeleniumOptions  # noqa: WPS433
            from selenium.webdriver.chrome.service import Service as SeleniumService  # noqa: WPS433
            from selenium.webdriver.common.by import By as SeleniumBy  # noqa: WPS433
            from selenium.webdriver.support.ui import WebDriverWait as SeleniumWait  # noqa: WPS433
            from selenium.webdriver.support import expected_conditions as SeleniumEC  # noqa: WPS433

            # Пробрасываем в модуль, т.к. при первичной загрузке uc уже импортирован
            cz.webdriver = selenium_webdriver
            cz.Options = SeleniumOptions
            cz.Service = SeleniumService
            cz.By = SeleniumBy
            cz.WebDriverWait = SeleniumWait
            cz.EC = SeleniumEC
        except Exception as import_err:  # noqa: BLE001
            print(f"❌ Не удалось импортировать selenium fallback: {import_err}")
            raise

        if not cz.selenium_available:
            print("❌ Selenium недоступен в окружении — fallback невозможен.")
            raise

        if args.no_fallback:
            print("🚫 Флаг --no-fallback активен, прерываемся после неудачи undetected.")
            raise

        # В headless режиме обычный Selenium работает стабильнее в CI
        try:
            html = run_once(args, headless=True)
        except Exception as exc2:  # noqa: BLE001
            print("-" * 80)
            print(f"❌ Ошибка fallback: {exc2}")
            print("Смотрите логи выше и /tmp/cloudflare_turnstile_attempt_*.png")
            print("-" * 80)
            raise

        chinese_chars = len([c for c in html if "\u4e00" <= c <= "\u9fff"])
        print("-" * 80)
        print(f"✅ Страница загружена: {len(html)} символов, китайских: {chinese_chars}")
        print("-" * 80)


if __name__ == "__main__":
    main()
