import subprocess, datetime, psutil, platform
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="NetDiag Pro (Universal)")
reports_db = []

def cmd(args: list) -> str:
    """Универсальный запуск команд с учётом особенностей ОС."""
    os_name = platform.system()
    enc = 'cp866' if os_name == "Windows" else 'utf-8'
    try:
        return subprocess.run(args, capture_output=True, text=True, encoding=enc).stdout.strip()
    except Exception as e:
        return f"Execution Error: {e}"

def run_bg_checks(client_ip: str, rdp_status: str, dns_provider: str, screen: str):
    """Сетевые тесты и сбор метрик."""
    time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Добавили проверку занятости диска
    disk = psutil.disk_usage('/').percent
    stats = f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}% | DISK: {disk}%"
    os_type = platform.system()

    if os_type == "Windows":
        mtu_cmd = ["ping", "-f", "-l", "1472", client_ip]
        ping_cmd = ["ping", "-n", "20", client_ip]
        trace_cmd = ["tracert", "-d", client_ip]
    elif os_type == "Darwin":
        mtu_cmd = ["ping", "-D", "-s", "1472", "-c", "4", client_ip]
        ping_cmd = ["ping", "-c", "20", client_ip]
        trace_cmd = ["traceroute", "-n", client_ip]
    else:
        mtu_cmd = ["ping", "-M", "do", "-s", "1472", "-c", "4", client_ip]
        ping_cmd = ["ping", "-c", "20", client_ip]
        trace_cmd = ["traceroute", "-n", client_ip]

    log = (
        f"[{time_now}] CLIENT: {client_ip} | SERVER OS: {os_type}\n"
        f" > DNS: {dns_provider}\n"
        f" > RDP: {rdp_status}\n"
        f" > SCREEN: {screen}\n"
        f" SERVER LOAD: {stats}\n"
        f"--- MTU TEST (1472B) ---\n{cmd(mtu_cmd)}\n"
        f"--- PING (20 PKTS) ---\n{cmd(ping_cmd)}\n"
        f"--- TRACE ROUTE ---\n{cmd(trace_cmd)}\n"
        f"{'='*60}"
    )
    
    # Сохраняем в оперативную память для /admin
    reports_db.append(log)
    
    # Сохраняем в текстовый файл для надежности
    with open("netdiag.log", "a", encoding="utf-8") as f:
        f.write(log + "\n\n")
        
    print(f"\n[+] New report generated for {client_ip}")

@app.get("/client", response_class=HTMLResponse)
def client_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Network Quality Test</title></head>
    <body style="font-family:sans-serif; text-align:center; padding-top:50px; color:#333;">
        <h2 id="m">Analyzing your connection...</h2>
        <p id="s">This will take about 20 seconds. Please keep this page open.</p>
        <script>
            async function run() {
                let dns = "Check Failed", rdp = "Unknown";
                
                // Собираем разрешение экрана пользователя
                let screenRes = window.screen.width + "x" + window.screen.height;
                
                try {
                    let res = await fetch('https://edns.ip-api.com/json');
                    let d = await res.json();
                    if (d.dns && d.dns.geo) dns = d.dns.geo + " (AS" + d.dns.asn + ")";
                } catch(e) {}
                
                let start = Date.now();
                try {
                    await fetch(window.location.protocol + "//" + window.location.hostname + ":3389", {mode:'no-cors', cache:'no-cache'});
                    rdp = "Open";
                } catch(e) {
                    rdp = (Date.now() - start < 3000) ? "Open" : "Blocked/Timeout";
                }
                
                // Передаем все собранные данные на сервер
                await fetch(`/submit?rdp=${encodeURIComponent(rdp)}&dns=${encodeURIComponent(dns)}&screen=${encodeURIComponent(screenRes)}`);
                
                document.getElementById('m').innerText = "✅ Analysis Finished!";
                document.getElementById('m').style.color = "green";
                document.getElementById('s').innerText = "Results sent to the administrator. You can close this tab.";
            }
            window.onload = run;
        </script>
    </body>
    </html>
    """

@app.get("/submit")
def submit(request: Request, bg_tasks: BackgroundTasks, rdp: str="Unknown", dns: str="Unknown", screen: str="Unknown"):
    bg_tasks.add_task(run_bg_checks, request.client.host, rdp, dns, screen)
    return {"status": "ok"}

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    content = "\n\n".join(reversed(reports_db)) if reports_db else "No reports yet..."
    return f"<html><body style='background:#1e1e1e;color:#4ec9b0;padding:20px;'><pre>{content}</pre></body></html>"
