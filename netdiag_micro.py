import subprocess
import datetime
import psutil
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse

# Инициализация веб-сервера
app = FastAPI(title="Micro NetDiag")

# Простая база данных в оперативной памяти для хранения отчетов.
# Очищается при перезапуске процесса Uvicorn.
reports_db = []

def get_server_resources() -> str:
    """
    Мгновенное снятие метрик сервера (VPS).
    Возвращает текущую загрузку процессора и оперативной памяти.
    """
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    return f"CPU: {cpu}% | RAM: {ram.percent}%"

def run_bg_checks(client_ip: str, rdp_status: str, dns_provider: str):
    """
    Главная фоновая задача. Выполняет сетевую диагностику со стороны сервера
    в сторону клиента через штатные системные утилиты Windows.
    """
    time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stats = get_server_resources()
    
    # 1. Запуск Ping (отправляем 4 пакета)
    try:
        ping = subprocess.run(
            ["ping", "-n", "4", client_ip], 
            capture_output=True, text=True, encoding='cp866'
        ).stdout.strip()
    except Exception:
        ping = "Ошибка выполнения Ping"

    # 2. Запуск Tracert
    # Флаг '-d' отключает определение DNS-имен магистральных роутеров для ускорения.
    # Количество прыжков не ограничивается, чтобы проследить весь трансатлантический маршрут.
    try:
        tracert = subprocess.run(
            ["tracert", "-d", client_ip], 
            capture_output=True, text=True, encoding='cp866'
        ).stdout.strip()
    except Exception:
        tracert = "Ошибка выполнения Tracert"

    # Сборка итогового текстового отчета
    log = (
        f"[{time_now}] КЛИЕНТ: {client_ip}\n"
        f" > DNS-резолвер: {dns_provider}\n"
        f" > RDP (3389):   {rdp_status}\n"
        f"РЕСУРСЫ VPS: {stats}\n"
        f"--- PING ---\n{ping}\n"
        f"--- TRACERT ---\n{tracert}\n"
        f"{'='*60}"
    )
    
    # Сохраняем в память и выводим в консоль сервера
    reports_db.append(log)
    print(f"\n[+] Новый отчет сохранен:\n{log}")


@app.get("/client", response_class=HTMLResponse)
def client_page():
    """
    Стартовая точка для пользователя (Agentless Client).
    Отдает браузеру HTML с JavaScript-логикой для проверки DNS и доступности порта 3389.
    """
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Диагностика сети</title>
        <style>
            body { font-family: sans-serif; text-align: center; padding-top: 50px; background: #f4f4f9; color: #333; }
            .loader { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
    </head>
    <body>
        <h2>Идет проверка связи с сервером...</h2>
        <div class="loader"></div>
        <p>Пожалуйста, подождите несколько секунд.</p>
        
        <script>
            async function runDiagnostics() {
                let dnsProvider = "Ошибка (Сбой связи с публичным DNS)";
                let rdpStatus = "Неизвестно";

                // 1. Проверка работы DNS и определение провайдера клиента
                try {
                    let dnsRes = await fetch('https://edns.ip-api.com/json');
                    let dnsData = await dnsRes.json();
                    if (dnsData.dns && dnsData.dns.geo) {
                        dnsProvider = dnsData.dns.geo + " (AS" + dnsData.dns.asn + ")";
                    }
                } catch(e) {
                    console.error("DNS Check Failed", e);
                }

                // 2. Timing Attack: проверка доступности порта RDP (3389)
                const startTime = Date.now();
                try {
                    await fetch(window.location.protocol + "//" + window.location.hostname + ":3389", {mode: 'no-cors', cache: 'no-cache'});
                    rdpStatus = "Открыт";
                } catch(e) {
                    // Если сброс соединения произошел быстрее чем за 3 секунды - порт открыт
                    // Если запрос висел дольше - порт заблокирован на уровне провайдера
                    const elapsed = Date.now() - startTime;
                    rdpStatus = (elapsed < 3000) ? "Открыт" : "Таймаут (Заблокирован)";
                }

                // Перенаправляем клиента на страницу финиша, передавая данные в URL
                const targetUrl = `/finish?rdp=${encodeURIComponent(rdpStatus)}&dns=${encodeURIComponent(dnsProvider)}`;
                window.location.href = targetUrl;
            }

            // Запускаем проверки сразу после загрузки страницы
            window.onload = runDiagnostics;
        </script>
    </body>
    </html>
    """


@app.get("/finish", response_class=HTMLResponse)
def finish_page(request: Request, bg_tasks: BackgroundTasks, rdp: str = "Неизвестно", dns: str = "Неизвестно"):
    """
    Эндпоинт приема данных. Сюда браузер клиента передает статус RDP и данные о DNS.
    Сервер отвечает пользователю и отправляет тяжелые проверки в фоновый поток.
    """
    client_ip = request.client.host
    
    # Передаем задачу в очередь FastAPI, чтобы не заставлять браузер ждать окончания Tracert
    bg_tasks.add_task(run_bg_checks, client_ip, rdp, dns)
    
    return """
    <html>
    <body style="font-family:sans-serif; text-align:center; padding-top:50px; background:#f4f4f9; color:green;">
        <h2>✅ Диагностика успешно завершена!</h2>
        <p>Данные переданы администратору. Эту страницу можно закрыть.</p>
    </body>
    </html>
    """


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    """
    Панель мониторинга для администратора.
    Выводит логи из оперативной памяти в обратном хронологическом порядке.
    """
    if not reports_db:
        content = "Ожидание подключений клиентов..."
    else:
        # Склеиваем список логов, разворачивая его (свежие записи сверху)
        content = "\n\n".join(reversed(reports_db))
        
    return f"<html><body style='background:#1e1e1e; color:#4ec9b0; padding:20px;'><pre>{content}</pre></body></html>"