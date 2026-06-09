import os
import json
import time
import datetime
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN  = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
HORARIO = os.environ.get("HORARIO_AVISO", "09:00")
DATA_FILE = "amigos.json"

# ── Dados ──────────────────────────────────────────────────────────────────
def carregar_amigos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_amigos(amigos):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(amigos, f, ensure_ascii=False, indent=2)

# ── Telegram ───────────────────────────────────────────────────────────────
def enviar_mensagem(texto):
    if not TOKEN or not CHAT_ID:
        print("Token ou Chat ID não configurado.")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    res = requests.post(url, json={"chat_id": CHAT_ID, "text": texto})
    return res.json().get("ok", False)

# ── Verificação diária ─────────────────────────────────────────────────────
ultimo_aviso = {}

def verificar_aniversarios():
    while True:
        agora = datetime.datetime.now()
        hora_atual = agora.strftime("%H:%M")
        hoje = (agora.month, agora.day)
        chave = f"{agora.date()}-{HORARIO}"

        if hora_atual == HORARIO and chave not in ultimo_aviso:
            ultimo_aviso[chave] = True
            amigos = carregar_amigos()
            for a in amigos:
                partes = a["data"].split("-")
                m, d = int(partes[1]), int(partes[2])
                if (m, d) == hoje:
                    nome = a.get("apelido") or a["nome"]
                    texto = (
                        f"🎂 Aniversário hoje!\n\n"
                        f"🎉 {a['nome']} faz aniversário hoje!\n"
                        f"Não esqueça de mandar uma mensagem para {nome}!"
                    )
                    ok = enviar_mensagem(texto)
                    print(f"[{agora}] Aviso enviado para {a['nome']}: {ok}")

        time.sleep(30)

# ── Servidor web simples (Railway exige uma porta aberta) ──────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silenciar logs

    def do_GET(self):
        amigos = carregar_amigos()
        if self.path == "/amigos":
            body = json.dumps(amigos, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot de Aniversarios rodando!")

    def do_POST(self):
        if self.path == "/amigos":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                amigos = json.loads(body)
                salvar_amigos(amigos)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

if __name__ == "__main__":
    # Inicia verificador em thread separada
    t = threading.Thread(target=verificar_aniversarios, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 8080))
    print(f"Servidor rodando na porta {port}...")
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()
