import subprocess
import datetime
import psutil
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI(title="Micro NetDiag")

# Хранилище логов в оперативной памяти
reports_db = []

def get_server_resources() -> str:
    """Быстрый замер CPU и RAM."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    return f"CPU: {cpu}% | RAM: {ram.percent}%"

def run_bg_checks(client_ip: str, rdp_status: str):
    """Выполняет тяжелые проверки (Ping/Tracert) в фоне и пишет лог."""
    time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stats = get_server_resources()
    
    # Пингуем клиента (4 пакета)
    try:
        ping = subprocess.run(["ping", "-n", "4", client_ip], capture_output=True, text=True, encoding='cp866').stdout.strip()
    except Exception:
        ping = "Ошибка Ping"

    # Трассировка (10 прыжков для скорости)
    try:
        tracert = subprocess.run(["tracert", "-d", "-h", "10", client_ip], capture_output=True, text=True, encoding='cp866').stdout.strip()
    except Exception:
        tracert = "Ошибка Tracert"

    # Формируем итоговый текстовый лог
    log = (
        f"[{time_now}] КЛИЕНТ: {client_ip} | RDP (3389): {rdp_status}\n"
        f"РЕСУРСЫ VPS: {stats}\n"
        f"--- PING ---\n{ping}\n"
        f"--- TRACERT ---\n{tracert}\n"
        f"{'='*60}"
    )
    
    reports_db.append(log)
    print(f"\n[+] Новый отчет сохранен:\n{log}")


@app.get("/client", response_class=HTMLResponse)
def client_page():
    """Стартовая страница клиента"""
    return """
    <html><body style="font-family:sans-serif; text-align:center; padding-top:50px; background:#f4f4f9;">
        <h2>Идет проверка связи с сервером...</h2>
        <script>
            // Cтучимся на порт 3389 и смотрим время ответа
            const start = Date.now();
            fetch(window.location.protocol + "//" + window.location.hostname + ":3389", {mode: 'no-cors'})
                .finally(() => {
                    // Если ответ быстрый (< 3 сек) - порт открыт. Если зависло - заблокирован.
                    const rdp = (Date.now() - start < 3000) ? "Открыт" : "Таймаут (Заблокирован)";
                    // Просто перенаправляем клиента на страницу финиша с результатом!
                    window.location.href = `/finish?rdp=${rdp}`;
                });
        </script>
    </body></html>
    """

@app.get("/finish", response_class=HTMLResponse)
def finish_page(request: Request, bg_tasks: BackgroundTasks, rdp: str = "Неизвестно"):
    """Страница финиша. Принимает результат RDP и запускает Ping в фоне."""
    client_ip = request.client.host
    
    # Отправляем задачу в фон, чтобы браузер не висел
    bg_tasks.add_task(run_bg_checks, client_ip, rdp)
    
    return """
    <html><body style="font-family:sans-serif; text-align:center; padding-top:50px; background:#f4f4f9; color:green;">
        <h2>✅ Диагностика успешно завершена!</h2>
        <p>Данные переданы администратору. Эту страницу можно закрыть.</p>
    </body></html>
    """

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    """Минималистичная админка для просмотра логов."""
    content = "\n\n".join(reversed(reports_db)) if reports_db else "Ожидание подключений..."
    return f"<html><body style='background:#1e1e1e; color:#4ec9b0; padding:20px;'><pre>{content}</pre></body></html>"