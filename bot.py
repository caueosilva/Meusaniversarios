import os
import json
import time
import datetime
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
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
def enviar_mensagem(texto, chat_id=None):
    cid = chat_id or CHAT_ID
    if not TOKEN or not cid:
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    res = requests.post(url, json={"chat_id": cid, "text": texto})
    return res.json().get("ok", False)

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        res = requests.get(url, params=params, timeout=35)
        return res.json().get("result", [])
    except:
        return []

# ── Comandos ───────────────────────────────────────────────────────────────
MESES = {
    "jan":1,"fev":2,"mar":3,"abr":4,"mai":5,"jun":6,
    "jul":7,"ago":8,"set":9,"out":10,"nov":11,"dez":12
}

def cmd_add(args, chat_id):
    # Uso: /add Nome 15/06  ou  /add Nome 15/06/1990
    if len(args) < 2:
        enviar_mensagem("Uso correto: /add Nome 15/06\nExemplo: /add Maria 23/04", chat_id)
        return
    nome = args[0]
    data_str = args[1]
    partes = data_str.split("/")
    if len(partes) < 2:
        enviar_mensagem("Data inválida. Use o formato DD/MM. Exemplo: 23/04", chat_id)
        return
    d, m = partes[0].zfill(2), partes[1].zfill(2)
    ano = partes[2] if len(partes) > 2 else "2000"
    data_iso = f"{ano}-{m}-{d}"

    amigos = carregar_amigos()
    amigos.append({"id": str(int(time.time())), "nome": nome, "data": data_iso})
    salvar_amigos(amigos)

    meses_pt = ["","Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    enviar_mensagem(f"✅ {nome} adicionado!\nAniversário: {int(d)} de {meses_pt[int(m)]}", chat_id)

def cmd_lista(chat_id):
    amigos = carregar_amigos()
    if not amigos:
        enviar_mensagem("Nenhum amigo cadastrado ainda.\nUse /add Nome DD/MM para adicionar.", chat_id)
        return

    hoje = datetime.date.today()
    def dias_para(a):
        m, d = int(a["data"].split("-")[1]), int(a["data"].split("-")[2])
        prox = datetime.date(hoje.year, m, d)
        if prox < hoje:
            prox = datetime.date(hoje.year + 1, m, d)
        return (prox - hoje).days

    meses_pt = ["","Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    ordenados = sorted(amigos, key=dias_para)
    linhas = ["🎂 *Seus aniversários:*\n"]
    for a in ordenados:
        m, d = int(a["data"].split("-")[1]), int(a["data"].split("-")[2])
        dias = dias_para(a)
        if dias == 0:
            badge = " 🎉 HOJE!"
        elif dias <= 7:
            badge = f" (em {dias} dias)"
        else:
            badge = ""
        linhas.append(f"• {a['nome']} — {d} de {meses_pt[m]}{badge}")

    enviar_mensagem("\n".join(linhas), chat_id)

def cmd_del(args, chat_id):
    if not args:
        enviar_mensagem("Uso correto: /del Nome\nExemplo: /del Maria", chat_id)
        return
    nome = " ".join(args).lower()
    amigos = carregar_amigos()
    novos = [a for a in amigos if a["nome"].lower() != nome]
    if len(novos) == len(amigos):
        enviar_mensagem(f"Nenhum amigo encontrado com o nome '{' '.join(args)}'.", chat_id)
    else:
        salvar_amigos(novos)
        enviar_mensagem(f"✅ {' '.join(args)} removido com sucesso.", chat_id)

def cmd_ajuda(chat_id):
    texto = (
        "🎂 *Bot de Aniversários — Comandos:*\n\n"
        "/add Nome DD/MM — Adicionar aniversário\n"
        "Exemplo: /add Maria 23/04\n\n"
        "/lista — Ver todos os aniversários\n\n"
        "/del Nome — Remover um amigo\n"
        "Exemplo: /del Maria\n\n"
        "/ajuda — Ver esta mensagem"
    )
    enviar_mensagem(texto, chat_id)

# ── Loop de comandos ───────────────────────────────────────────────────────
def ouvir_comandos():
    offset = None
    print("Ouvindo comandos do Telegram...")
    while True:
        updates = get_updates(offset)
        for u in updates:
            offset = u["update_id"] + 1
            msg = u.get("message", {})
            texto = msg.get("text", "")
            chat_id = str(msg.get("chat", {}).get("id", ""))
            if not texto or not chat_id:
                continue

            partes = texto.strip().split()
            cmd = partes[0].lower().split("@")[0]
            args = partes[1:]

            if cmd == "/add":
                cmd_add(args, chat_id)
            elif cmd == "/lista":
                cmd_lista(chat_id)
            elif cmd == "/del":
                cmd_del(args, chat_id)
            elif cmd == "/ajuda" or cmd == "/start":
                cmd_ajuda(chat_id)
        time.sleep(1)

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
                m, d = int(a["data"].split("-")[1]), int(a["data"].split("-")[2])
                if (m, d) == hoje:
                    nome = a.get("apelido") or a["nome"]
                    texto = (
                        f"🎂 Aniversário hoje!\n\n"
                        f"🎉 {a['nome']} faz aniversário hoje!\n"
                        f"Não esqueça de mandar uma mensagem para {nome}!"
                    )
                    enviar_mensagem(texto)
                    print(f"[{agora}] Aviso enviado: {a['nome']}")
        time.sleep(30)

# ── Servidor web ───────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot de Aniversarios rodando!")

if __name__ == "__main__":
    threading.Thread(target=ouvir_comandos, daemon=True).start()
    threading.Thread(target=verificar_aniversarios, daemon=True).start()

    port = int(os.environ.get("PORT", 8080))
    print(f"Servidor na porta {port}...")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
