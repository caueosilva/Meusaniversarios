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
        print(f"ERRO: Token={bool(TOKEN)} ChatID={bool(cid)}")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": cid, "text": texto}, timeout=10)
        data = res.json()
        if not data.get("ok"):
            print(f"Telegram erro: {data}")
        return data.get("ok", False)
    except Exception as e:
        print(f"Erro ao enviar: {e}")
        return False

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 5, "offset": offset} if offset else {"timeout": 5}
    try:
        res = requests.get(url, params=params, timeout=10)
        return res.json().get("result", [])
    except Exception as e:
        print(f"Erro getUpdates: {e}")
        return []

def pular_mensagens_antigas():
    updates = get_updates()
    if not updates:
        return None
    ultimo = updates[-1]["update_id"]
    print(f"Pulando {len(updates)} mensagens antigas.")
    return ultimo + 1

# ── Comandos Telegram ──────────────────────────────────────────────────────
def cmd_add(args, chat_id):
    if len(args) < 2:
        enviar_mensagem("Uso: /add Nome DD/MM\nExemplo: /add Maria 23/04", chat_id)
        return
    nome = " ".join(args[:-1])
    data_str = args[-1]
    partes = data_str.split("/")
    if len(partes) < 2:
        enviar_mensagem("Data inválida. Use DD/MM. Exemplo: 23/04", chat_id)
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
        enviar_mensagem("Nenhum amigo cadastrado.\nUse /add Nome DD/MM para adicionar.", chat_id)
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
    linhas = ["🎂 Seus aniversários:\n"]
    for a in ordenados:
        m, d = int(a["data"].split("-")[1]), int(a["data"].split("-")[2])
        dias = dias_para(a)
        badge = " 🎉 HOJE!" if dias == 0 else (f" (em {dias} dias)" if dias <= 7 else "")
        linhas.append(f"• {a['nome']} — {d} de {meses_pt[m]}{badge}")
    enviar_mensagem("\n".join(linhas), chat_id)

def cmd_del(args, chat_id):
    if not args:
        enviar_mensagem("Uso: /del Nome\nExemplo: /del Maria", chat_id)
        return
    nome = " ".join(args).lower()
    amigos = carregar_amigos()
    novos = [a for a in amigos if a["nome"].lower() != nome]
    if len(novos) == len(amigos):
        enviar_mensagem(f"Nenhum amigo com o nome '{' '.join(args)}' encontrado.", chat_id)
    else:
        salvar_amigos(novos)
        enviar_mensagem(f"✅ {' '.join(args)} removido.", chat_id)

def cmd_ajuda(chat_id):
    enviar_mensagem(
        "🎂 Bot de Aniversários\n\n"
        "/add Nome DD/MM — Adicionar\n"
        "Ex: /add Maria 23/04\n\n"
        "/lista — Ver todos\n\n"
        "/del Nome — Remover\n"
        "Ex: /del Maria\n\n"
        "/teste — Simular aviso\n\n"
        "/ajuda — Ver comandos",
        chat_id
    )

def cmd_teste(chat_id):
    amigos = carregar_amigos()
    if not amigos:
        enviar_mensagem("Nenhum amigo cadastrado ainda.", chat_id)
        return
    hoje = datetime.date.today()
    def dias_para(a):
        m, d = int(a["data"].split("-")[1]), int(a["data"].split("-")[2])
        prox = datetime.date(hoje.year, m, d)
        if prox < hoje:
            prox = datetime.date(hoje.year + 1, m, d)
        return (prox - hoje).days
    proximo = sorted(amigos, key=dias_para)[0]
    nome = proximo.get("apelido") or proximo["nome"]
    enviar_mensagem(
        f"🔔 Isso é um TESTE:\n\n"
        f"🎂 Aniversário hoje!\n\n"
        f"🎉 {proximo['nome']} faz aniversário hoje!\n"
        f"Não esqueça de mandar uma mensagem para {nome}!",
        chat_id
    )

# ── Loop de comandos ───────────────────────────────────────────────────────
def ouvir_comandos():
    print("Iniciando... pulando mensagens antigas.")
    offset = pular_mensagens_antigas()
    print(f"Pronto! Ouvindo a partir do offset {offset}")
    while True:
        try:
            updates = get_updates(offset)
            for u in updates:
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                texto = msg.get("text", "").strip()
                chat_id = str(msg.get("chat", {}).get("id", ""))
                if not texto or not chat_id:
                    continue
                print(f"Mensagem: '{texto}' de {chat_id}")
                partes = texto.split()
                cmd = partes[0].lower().split("@")[0]
                args = partes[1:]
                if cmd == "/add":           cmd_add(args, chat_id)
                elif cmd == "/lista":        cmd_lista(chat_id)
                elif cmd == "/del":          cmd_del(args, chat_id)
                elif cmd == "/teste":        cmd_teste(chat_id)
                elif cmd in ("/ajuda", "/start"): cmd_ajuda(chat_id)
                else: enviar_mensagem("Comando não reconhecido. Use /ajuda.", chat_id)
        except Exception as e:
            print(f"Erro no loop: {e}")
        time.sleep(2)

# ── Verificação diária ─────────────────────────────────────────────────────
ultimo_aviso = {}

def verificar_aniversarios():
    while True:
        try:
            agora = datetime.datetime.now()
            hora_atual = agora.strftime("%H:%M")
            hoje = (agora.month, agora.day)
            chave = f"{agora.date()}-{HORARIO}"
            if hora_atual == HORARIO and chave not in ultimo_aviso:
                ultimo_aviso[chave] = True
                for a in carregar_amigos():
                    m, d = int(a["data"].split("-")[1]), int(a["data"].split("-")[2])
                    if (m, d) == hoje:
                        nome = a.get("apelido") or a["nome"]
                        enviar_mensagem(
                            f"🎂 Aniversário hoje!\n\n"
                            f"🎉 {a['nome']} faz aniversário hoje!\n"
                            f"Não esqueça de mandar uma mensagem para {nome}!"
                        )
        except Exception as e:
            print(f"Erro verificação: {e}")
        time.sleep(30)

# ── Servidor web com API ───────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/amigos":
            body = json.dumps(carregar_amigos(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/horario":
            body = json.dumps({"horario": HORARIO}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)
        else:
            html = '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">\n<meta name="apple-mobile-web-app-capable" content="yes">\n<title>🎂 Meus Aniversários</title>\n<style>\n@import url(\'https://fonts.googleapis.com/css2?family=Fraunces:wght@400;700;900&family=DM+Sans:wght@400;500;600&display=swap\');\n:root{--cake:#FF6B6B;--candle:#FFD166;--mint:#06D6A0;--dark:#1A1A2E;--mid:#2D2D44;--card:#252540;--text:#E8E8F0;--muted:#888899;--border:#3A3A55}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:\'DM Sans\',sans-serif;background:var(--dark);color:var(--text);min-height:100vh;padding-bottom:80px}\nheader{background:var(--card);border-bottom:1px solid var(--border);padding:20px 20px 16px;position:sticky;top:0;z-index:10}\nheader h1{font-family:\'Fraunces\',serif;font-size:1.5rem;font-weight:900;color:var(--candle);letter-spacing:-.5px}\n.status-bar{display:flex;align-items:center;gap:6px;margin-top:4px;font-size:.78rem;color:var(--muted)}\n.dot{width:7px;height:7px;border-radius:50%;background:var(--muted)}\n.dot.online{background:var(--mint);box-shadow:0 0 5px var(--mint)}\n.container{max-width:480px;margin:0 auto;padding:16px;display:flex;flex-direction:column;gap:14px}\n.add-card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:18px}\n.add-card h2{font-family:\'Fraunces\',serif;font-size:1rem;margin-bottom:14px}\n.field{margin-bottom:12px}\nlabel{display:block;font-size:.75rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px}\ninput,select{width:100%;background:var(--mid);border:1px solid var(--border);border-radius:10px;padding:11px 13px;color:var(--text);font-family:\'DM Sans\',sans-serif;font-size:.95rem;outline:none;transition:border-color .2s;-webkit-appearance:none}\ninput:focus{border-color:var(--candle)}\n.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}\n.btn{font-family:\'DM Sans\',sans-serif;font-weight:600;border:none;cursor:pointer;border-radius:10px;transition:opacity .15s,transform .1s;font-size:.95rem}\n.btn:active{transform:scale(.97)}\n.btn-primary{background:var(--candle);color:var(--dark);padding:12px;width:100%}\n.btn-primary:disabled{opacity:.4;cursor:not-allowed}\n.msg{font-size:.82rem;border-radius:8px;padding:9px 12px;margin-top:10px;display:none}\n.msg.ok{background:#06D6A022;color:var(--mint);border:1px solid var(--mint);display:block}\n.msg.err{background:#FF6B6B22;color:var(--cake);border:1px solid var(--cake);display:block}\n.list-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}\n.list-header h2{font-family:\'Fraunces\',serif;font-size:1rem}\n.count{background:var(--mid);color:var(--muted);font-size:.75rem;font-weight:600;padding:2px 8px;border-radius:20px}\n.friend-list{display:flex;flex-direction:column;gap:8px}\n.friend-item{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:13px 14px;display:flex;align-items:center;justify-content:space-between;gap:10px;animation:fadeIn .2s ease}\n@keyframes fadeIn{from{opacity:0;transform:translateY(5px)}to{opacity:1}}\n.friend-left{display:flex;align-items:center;gap:11px}\n.avatar{width:38px;height:38px;border-radius:50%;background:var(--mid);display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0}\n.friend-info strong{font-size:.92rem;display:block}\n.friend-info span{font-size:.78rem;color:var(--muted)}\n.badge{font-size:.7rem;font-weight:600;padding:2px 7px;border-radius:20px;margin-left:5px}\n.badge.hoje{background:var(--mint);color:var(--dark)}\n.badge.soon{background:var(--candle);color:var(--dark)}\n.btn-del{background:transparent;border:1px solid var(--border);color:var(--muted);padding:6px 10px;font-size:.8rem;border-radius:8px;flex-shrink:0}\n.btn-del:hover{border-color:var(--cake);color:var(--cake)}\n.empty{text-align:center;padding:32px 0;color:var(--muted);font-size:.9rem;background:var(--card);border:1px solid var(--border);border-radius:12px}\n.loading{text-align:center;padding:24px;color:var(--muted);font-size:.88rem;animation:pulse 1.2s infinite}\n@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}\n.horario-info{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:13px 16px;font-size:.85rem;color:var(--muted);display:flex;align-items:center;gap:8px}\n.horario-info strong{color:var(--candle)}\n</style>\n</head>\n<body>\n<header>\n  <h1>🎂 Meus Aniversários</h1>\n  <div class="status-bar">\n    <div id="dot" class="dot"></div>\n    <span id="statusText">Conectando...</span>\n  </div>\n</header>\n<div class="container">\n  <div class="horario-info">⏰ Avisos enviados às <strong id="horarioLabel">--:--</strong> no Telegram</div>\n  <div class="add-card">\n    <h2>➕ Adicionar amigo</h2>\n    <div class="field"><label>Nome completo</label><input type="text" id="nome" placeholder="Ex: Matheus Cossulindo"/></div>\n    <div class="row">\n      <div class="field"><label>Dia</label><input type="number" id="dia" placeholder="21" min="1" max="31"/></div>\n      <div class="field"><label>Mês</label>\n        <select id="mes">\n          <option value="01">Janeiro</option><option value="02">Fevereiro</option><option value="03">Março</option>\n          <option value="04">Abril</option><option value="05">Maio</option><option value="06">Junho</option>\n          <option value="07">Julho</option><option value="08">Agosto</option><option value="09">Setembro</option>\n          <option value="10">Outubro</option><option value="11">Novembro</option><option value="12">Dezembro</option>\n        </select>\n      </div>\n    </div>\n    <button class="btn btn-primary" id="btnAdd" onclick="adicionar()">Adicionar</button>\n    <div id="msgAdd" class="msg"></div>\n  </div>\n  <div>\n    <div class="list-header"><h2>🎉 Aniversários</h2><span class="count" id="total">0</span></div>\n    <div class="friend-list" id="lista"><div class="loading">Carregando...</div></div>\n  </div>\n</div>\n<script>\nconst MESES=["","Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];\nfunction setOnline(ok){document.getElementById("dot").className="dot"+(ok?" online":"");document.getElementById("statusText").textContent=ok?"Bot online ✓":"Sem conexão"}\nasync function carregarHorario(){try{const r=await fetch("/horario");const d=await r.json();document.getElementById("horarioLabel").textContent=d.horario||"09:00"}catch{}}\nasync function carregar(){try{const r=await fetch("/amigos");const a=await r.json();setOnline(true);renderLista(a)}catch{setOnline(false);document.getElementById("lista").innerHTML=\'<div class="empty">Erro ao carregar.<br>Tente recarregar a página.</div>\'}}\nfunction diasPara(iso){const hoje=new Date();hoje.setHours(0,0,0,0);const[,m,d]=iso.split("-");let p=new Date(hoje.getFullYear(),parseInt(m)-1,parseInt(d));if(p<hoje)p.setFullYear(hoje.getFullYear()+1);return Math.round((p-hoje)/86400000)}\nfunction renderLista(amigos){const l=document.getElementById("lista");document.getElementById("total").textContent=amigos.length;if(!amigos.length){l.innerHTML=\'<div class="empty">Nenhum amigo ainda.<br>Adicione o primeiro acima! ☝️</div>\';return}const ord=[...amigos].sort((a,b)=>diasPara(a.data)-diasPara(b.data));l.innerHTML=ord.map(a=>{const dias=diasPara(a.data);const[,m,d]=a.data.split("-");const badge=dias===0?\'<span class="badge hoje">🎂 Hoje!</span>\':dias<=7?`<span class="badge soon">em ${dias}d</span>`:"";return`<div class="friend-item"><div class="friend-left"><div class="avatar">${a.nome.charAt(0).toUpperCase()}</div><div class="friend-info"><strong>${a.nome}${badge}</strong><span>${parseInt(d)} de ${MESES[parseInt(m)]}</span></div></div><button class="btn btn-del" onclick="remover(\'${a.id}\')">✕</button></div>`}).join("")}\nasync function adicionar(){const nome=document.getElementById("nome").value.trim();const dia=document.getElementById("dia").value.trim().padStart(2,"0");const mes=document.getElementById("mes").value;const msg=document.getElementById("msgAdd");const btn=document.getElementById("btnAdd");if(!nome)return showMsg(msg,"Digite o nome do amigo.","err");if(!dia||parseInt(dia)<1||parseInt(dia)>31)return showMsg(msg,"Digite um dia válido (1-31).","err");btn.disabled=true;btn.textContent="Salvando...";try{const r=await fetch("/amigos",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:Date.now().toString(),nome,data:`2000-${mes}-${dia}`})});const d=await r.json();if(d.ok){showMsg(msg,`${nome} adicionado! 🎉`,"ok");document.getElementById("nome").value="";document.getElementById("dia").value="";carregar()}else showMsg(msg,"Erro ao salvar.","err")}catch{showMsg(msg,"Erro de conexão.","err")}btn.disabled=false;btn.textContent="Adicionar"}\nasync function remover(id){try{await fetch("/amigos/"+id,{method:"DELETE"});carregar()}catch{alert("Erro ao remover.")}}\nfunction showMsg(el,txt,tipo){el.textContent=txt;el.className="msg "+tipo;if(tipo==="ok")setTimeout(()=>el.className="msg",3000)}\ncarregar();carregarHorario();setInterval(carregar,30000);\n</script>\n</body>\n</html>\n'.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_cors()
            self.end_headers()
            self.wfile.write(html)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if self.path == "/amigos":
            try:
                amigo = json.loads(body)
                amigos = carregar_amigos()
                amigos.append(amigo)
                salvar_amigos(amigos)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.send_response(400)
                self.send_cors()
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith("/amigos/"):
            amigo_id = self.path.split("/amigos/")[1]
            amigos = carregar_amigos()
            novos = [a for a in amigos if a["id"] != amigo_id]
            salvar_amigos(novos)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    threading.Thread(target=ouvir_comandos, daemon=True).start()
    threading.Thread(target=verificar_aniversarios, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    print(f"Servidor na porta {port}...")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()