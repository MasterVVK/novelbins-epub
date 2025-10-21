/**
 * Cloudflare Authentication Helper
 * Открывает popup для прохождения Cloudflare challenge
 * и автоматически извлекает cookies
 */

class CloudflareAuth {
    constructor() {
        this.popup = null;
        this.checkInterval = null;
        this.onSuccess = null;
        this.onError = null;
    }

    /**
     * Открыть окно для прохождения Cloudflare challenge
     * @param {string} targetUrl - URL сайта для аутентификации
     * @param {function} onSuccess - Callback при успехе (cookies)
     * @param {function} onError - Callback при ошибке
     */
    openAuthWindow(targetUrl, onSuccess, onError) {
        this.onSuccess = onSuccess;
        this.onError = onError;

        // Открываем popup окно
        const width = 1200;
        const height = 800;
        const left = (screen.width / 2) - (width / 2);
        const top = (screen.height / 2) - (height / 2);

        const authUrl = `/api/cloudflare-auth/window?url=${encodeURIComponent(targetUrl)}`;

        this.popup = window.open(
            authUrl,
            'cloudflare_auth',
            `width=${width},height=${height},left=${left},top=${top},menubar=no,toolbar=no,location=no,status=no`
        );

        if (!this.popup) {
            this.onError && this.onError('Не удалось открыть окно. Проверьте, не блокирует ли браузер popup окна.');
            return;
        }

        // Слушаем сообщения от popup
        window.addEventListener('message', this.handleMessage.bind(this));

        // Проверяем, не закрыто ли окно
        this.checkInterval = setInterval(() => {
            if (this.popup && this.popup.closed) {
                this.cleanup();
                this.onError && this.onError('Окно было закрыто до завершения аутентификации');
            }
        }, 500);
    }

    handleMessage(event) {
        // Проверяем источник сообщения (должно быть от нашего окна)
        if (event.data && event.data.action) {
            switch (event.data.action) {
                case 'cloudflareSuccess':
                    console.log('Cloudflare authentication successful');
                    console.log('Cookies received:', event.data.cookies);
                    break;

                case 'cloudflareComplete':
                    console.log('Cloudflare authentication complete');
                    this.cleanup();

                    if (event.data.cookies) {
                        this.onSuccess && this.onSuccess(event.data.cookies);
                    } else {
                        this.onError && this.onError('Cookies не получены');
                    }
                    break;
            }
        }
    }

    cleanup() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }

        if (this.popup && !this.popup.closed) {
            this.popup.close();
        }

        this.popup = null;
    }

    /**
     * Показать модальное окно с кнопкой для запуска аутентификации
     * @param {string} targetUrl - URL сайта
     * @param {string} siteName - Название сайта
     * @param {function} onSuccess - Callback при успехе
     */
    showAuthModal(targetUrl, siteName, onSuccess) {
        // Создаем модальное окно Bootstrap
        const modalId = 'cloudflareAuthModal';
        let modal = document.getElementById(modalId);

        if (!modal) {
            const modalHTML = `
                <div class="modal fade" id="${modalId}" tabindex="-1">
                    <div class="modal-dialog modal-dialog-centered">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="bi bi-shield-check"></i> Cloudflare Authentication
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="alert alert-info">
                                    <i class="bi bi-info-circle"></i>
                                    <strong>Требуется пройти проверку Cloudflare</strong>
                                </div>
                                <p>
                                    Сайт <strong>${siteName}</strong> использует защиту Cloudflare.
                                    Нажмите кнопку ниже, чтобы пройти проверку безопасности.
                                </p>
                                <p class="small text-muted">
                                    Откроется новое окно, где вам нужно будет дождаться прохождения проверки (~5 секунд).
                                    После успешной проверки cookies будут автоматически сохранены.
                                </p>
                                <div id="cf-auth-status" class="mt-3" style="display: none;"></div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                    Отмена
                                </button>
                                <button type="button" class="btn btn-primary" id="start-cf-auth-btn">
                                    <i class="bi bi-shield-check"></i> Пройти проверку
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHTML);
            modal = document.getElementById(modalId);
        }

        // Показываем модальное окно
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        // Обработчик кнопки
        const startBtn = document.getElementById('start-cf-auth-btn');
        const statusDiv = document.getElementById('cf-auth-status');

        startBtn.onclick = () => {
            startBtn.disabled = true;
            startBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Открываем окно...';

            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '<div class="alert alert-warning mb-0">Ожидание прохождения проверки...</div>';

            this.openAuthWindow(
                targetUrl,
                (cookies) => {
                    // Успех
                    statusDiv.innerHTML = '<div class="alert alert-success mb-0">✅ Проверка пройдена! Cookies получены.</div>';
                    setTimeout(() => {
                        bsModal.hide();
                        onSuccess && onSuccess(cookies);
                    }, 1500);
                },
                (error) => {
                    // Ошибка
                    statusDiv.innerHTML = `<div class="alert alert-danger mb-0">❌ ${error}</div>`;
                    startBtn.disabled = false;
                    startBtn.innerHTML = '<i class="bi bi-shield-check"></i> Попробовать снова';
                }
            );
        };

        // Cleanup при закрытии
        modal.addEventListener('hidden.bs.modal', () => {
            this.cleanup();
        });
    }
}

// Экспортируем для использования
window.CloudflareAuth = CloudflareAuth;
