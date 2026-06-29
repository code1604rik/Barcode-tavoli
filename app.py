"""
BARCODE - Gestione Tavoli
Web app per segnare lo stato scontrino POS dei tavoli.

Due schermate:
  - Tastierino: scegli la modalita (Normale / Scontrino emesso), digiti il
    numero del tavolo e confermi. Aggiorna subito anche la griglia.
  - Tavoli: la griglia di tutti i tavoli, ogni tap cambia stato in ciclo
    (normale -> emesso -> incassato -> normale).

Avvio locale:   python app.py
Avvio Railway:  gestito dal Procfile con gunicorn
"""

import os
import json
import threading
from datetime import timedelta
from functools import wraps

from flask import Flask, request, session, redirect, url_for, jsonify, abort

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

NUM_TAVOLI = int(os.environ.get("NUM_TAVOLI", "50"))
STATI = ["normale", "emesso", "incassato"]
STATO_FILE = os.environ.get("STATO_FILE", "stato_tavoli.json")

# Password del personale e chiave di sessione: impostale su Railway (Variables).
PASSWORD = os.environ.get("APP_PASSWORD", "barcode")
SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-questa-chiave-segreta")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(hours=12)  # niente logout a meta turno

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Persistenza stato (file JSON)
# ---------------------------------------------------------------------------

def carica_stato():
    """Carica lo stato dal file, garantendo che tutti i tavoli esistano."""
    dati = {}
    if os.path.exists(STATO_FILE):
        try:
            with open(STATO_FILE, "r", encoding="utf-8") as f:
                dati = json.load(f)
        except (json.JSONDecodeError, OSError):
            dati = {}
    return {
        str(i): (dati.get(str(i)) if dati.get(str(i)) in STATI else "normale")
        for i in range(1, NUM_TAVOLI + 1)
    }


def salva_stato(stato):
    """Salva lo stato sul file in modo sicuro."""
    cartella = os.path.dirname(STATO_FILE)
    if cartella:
        os.makedirs(cartella, exist_ok=True)
    tmp = STATO_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stato, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATO_FILE)


# Stato in memoria (worker singolo -> coerente per tutti i dispositivi).
stato_tavoli = carica_stato()


# ---------------------------------------------------------------------------
# Autenticazione
# ---------------------------------------------------------------------------

def login_richiesto(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("autenticato"):
            if request.path.startswith("/api/"):
                return jsonify({"errore": "non autenticato"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Rotte
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    errore_html = ""
    if request.method == "POST":
        if request.form.get("password", "") == PASSWORD:
            session["autenticato"] = True
            session.permanent = True
            return redirect(url_for("index"))
        errore_html = '<p class="errore">Password errata. Riprova.</p>'
    return LOGIN_HTML.replace("__ERRORE__", errore_html)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_richiesto
def index():
    return INDEX_HTML.replace("__NUM_TAVOLI__", str(NUM_TAVOLI))


@app.route("/api/state")
@login_richiesto
def api_state():
    with _lock:
        return jsonify(dict(stato_tavoli))


@app.route("/api/table/<int:tavolo_id>", methods=["POST"])
@login_richiesto
def api_table(tavolo_id):
    """
    Senza corpo: cicla lo stato (usato dal tap sulla griglia).
    Con corpo JSON {"stato": "normale|emesso|incassato"}: imposta quello stato
    (usato dal tastierino).
    """
    if tavolo_id < 1 or tavolo_id > NUM_TAVOLI:
        abort(404)
    key = str(tavolo_id)
    dati = request.get_json(silent=True) or {}
    richiesto = dati.get("stato")
    with _lock:
        if richiesto in STATI:
            stato_tavoli[key] = richiesto
        else:
            attuale = stato_tavoli.get(key, "normale")
            stato_tavoli[key] = STATI[(STATI.index(attuale) + 1) % len(STATI)]
        nuovo = stato_tavoli[key]
        salva_stato(stato_tavoli)
    return jsonify({"tavolo": tavolo_id, "stato": nuovo})


@app.route("/api/reset", methods=["POST"])
@login_richiesto
def api_reset():
    with _lock:
        for k in stato_tavoli:
            stato_tavoli[k] = "normale"
        salva_stato(stato_tavoli)
        return jsonify(dict(stato_tavoli))


# ---------------------------------------------------------------------------
# Pagina di login
# ---------------------------------------------------------------------------

LOGIN_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0E0E11">
<title>Barcode — Accesso</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0E0E11; --surface:#17171C; --linea:#2A2A32;
    --testo:#F5F5F2; --muto:#8A8A94;
    --amber:#F5A623; --verde:#27C26E; --rosso:#E2574C;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{
    background:var(--bg); color:var(--testo);
    font-family:"Inter",system-ui,-apple-system,sans-serif;
    min-height:100dvh; display:grid; place-items:center; padding:24px;
  }
  .card{
    width:100%; max-width:360px; background:var(--surface);
    border:1px solid var(--linea); border-radius:18px; padding:34px 28px 30px;
  }
  .marchio{
    display:flex; flex-direction:column; align-items:center; gap:14px; margin-bottom:26px;
  }
  .barcode{
    width:120px; height:46px; border-radius:4px;
    background-image:repeating-linear-gradient(90deg,
      var(--testo) 0 2px, transparent 2px 5px,
      var(--testo) 5px 6px, transparent 6px 11px,
      var(--testo) 11px 14px, transparent 14px 16px,
      var(--testo) 16px 17px, transparent 17px 22px);
  }
  .wordmark{
    font-family:"Space Mono",monospace; font-weight:700; font-size:26px;
    letter-spacing:.36em; text-indent:.36em;
  }
  .eyebrow{
    font-family:"Space Mono",monospace; font-size:11px; letter-spacing:.28em;
    color:var(--muto); text-transform:uppercase;
  }
  label{
    display:block; font-size:12px; letter-spacing:.06em; color:var(--muto);
    text-transform:uppercase; margin-bottom:8px;
  }
  input[type=password]{
    width:100%; background:#0E0E11; border:1px solid var(--linea); border-radius:11px;
    color:var(--testo); font-size:17px; font-family:"Space Mono",monospace;
    padding:14px 15px; outline:none; transition:border-color .15s;
  }
  input[type=password]:focus{border-color:var(--amber)}
  button{
    width:100%; margin-top:16px; padding:14px; border:none; border-radius:11px;
    background:var(--testo); color:#0E0E11; font-family:"Inter",sans-serif;
    font-weight:600; font-size:15px; letter-spacing:.02em; cursor:pointer;
    transition:transform .08s, opacity .15s;
  }
  button:hover{opacity:.92}
  button:active{transform:scale(.98)}
  button:focus-visible{outline:2px solid var(--amber); outline-offset:2px}
  .errore{
    margin-top:14px; color:var(--rosso); font-size:13.5px; text-align:center;
  }
</style>
</head>
<body>
  <form class="card" method="POST" action="/login">
    <div class="marchio">
      <div class="barcode" aria-hidden="true"></div>
      <div class="wordmark">BARCODE</div>
      <div class="eyebrow">Gestione tavoli</div>
    </div>
    <label for="password">Password personale</label>
    <input id="password" name="password" type="password" autocomplete="current-password" autofocus required>
    <button type="submit">Entra</button>
    __ERRORE__
  </form>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Pagina principale (tastierino + griglia tavoli)
# ---------------------------------------------------------------------------

INDEX_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0E0E11">
<title>Barcode — Tavoli</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0E0E11; --surface:#17171C; --surface-hi:#1F1F26; --linea:#2A2A32;
    --testo:#F5F5F2; --muto:#8A8A94;
    --amber:#F5A623; --amber-soft:rgba(245,166,35,.14);
    --verde:#27C26E; --verde-soft:rgba(39,194,110,.15);
    --rosso:#E2574C; --normale-dot:#3A3A44;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{background:var(--bg); color:var(--testo);
    font-family:"Inter",system-ui,-apple-system,sans-serif;}
  body{min-height:100dvh; padding-bottom:env(safe-area-inset-bottom)}

  /* ---------- Header globale + navigazione ---------- */
  header{
    position:sticky; top:0; z-index:10; background:rgba(14,14,17,.92);
    backdrop-filter:blur(10px); border-bottom:1px solid var(--linea);
    padding:14px 18px;
  }
  .barra{display:flex; align-items:center; gap:16px; flex-wrap:wrap}
  .brand{display:flex; align-items:center; gap:12px; margin-right:auto}
  .barcode{
    width:42px; height:26px; border-radius:3px;
    background-image:repeating-linear-gradient(90deg,
      var(--testo) 0 1.5px, transparent 1.5px 4px,
      var(--testo) 4px 5px, transparent 5px 9px,
      var(--testo) 9px 11px, transparent 11px 13px,
      var(--testo) 13px 14px, transparent 14px 18px);
  }
  .titolo{display:flex; flex-direction:column; line-height:1.15}
  .wordmark{font-family:"Space Mono",monospace; font-weight:700; font-size:18px;
    letter-spacing:.26em; text-indent:.26em;}
  .eyebrow{font-family:"Space Mono",monospace; font-size:10px; letter-spacing:.22em;
    color:var(--muto); text-transform:uppercase;}

  .nav-tabs{display:flex; gap:5px; background:var(--surface);
    border:1px solid var(--linea); border-radius:12px; padding:4px}
  .nav-tab{padding:9px 18px; border-radius:9px; border:none; background:transparent;
    color:var(--muto); font-family:"Inter",sans-serif; font-weight:600; font-size:14px;
    cursor:pointer; transition:background .15s, color .15s}
  .nav-tab.attivo{background:var(--surface-hi); color:var(--testo)}
  .nav-tab:focus-visible{outline:2px solid var(--amber); outline-offset:2px}

  .azioni{display:flex; align-items:center; gap:10px}
  .stato-rete{display:flex; align-items:center; gap:7px; font-size:12px; color:var(--muto)}
  .led{width:9px; height:9px; border-radius:50%; background:var(--verde);
    animation:battito 2.4s infinite}
  .stato-rete.offline .led{background:var(--rosso); animation:none}
  @keyframes battito{0%{box-shadow:0 0 0 0 rgba(39,194,110,.45)}
    70%{box-shadow:0 0 0 6px rgba(39,194,110,0)}100%{box-shadow:0 0 0 0 rgba(39,194,110,0)}}
  .btn{
    border:1px solid var(--linea); background:var(--surface); color:var(--testo);
    font-family:"Inter",sans-serif; font-size:13px; font-weight:500;
    padding:9px 14px; border-radius:10px; cursor:pointer; text-decoration:none;
    transition:background .15s, transform .08s;
  }
  .btn:hover{background:var(--surface-hi)}
  .btn:active{transform:scale(.97)}
  .btn:focus-visible{outline:2px solid var(--amber); outline-offset:2px}

  main{padding:18px}

  /* ---------- Vista TASTIERINO ---------- */
  .tastierino{max-width:480px; margin:0 auto}
  .modalita{display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px}
  .mod-btn{
    display:flex; align-items:center; justify-content:center; gap:10px; min-height:66px;
    border:2px solid var(--linea); background:var(--surface); border-radius:16px;
    color:var(--muto); font-family:"Inter",sans-serif; font-weight:600; font-size:15px;
    cursor:pointer; transition:background .15s, border-color .15s, color .15s;
  }
  .mod-btn .pallino{width:15px; height:15px; border-radius:5px; flex:none}
  .mod-btn[data-mod="normale"] .pallino{background:var(--normale-dot)}
  .mod-btn[data-mod="emesso"] .pallino{background:var(--amber)}
  .mod-btn.attivo{color:var(--testo)}
  .mod-btn[data-mod="normale"].attivo{border-color:#5A5A66; background:var(--surface-hi)}
  .mod-btn[data-mod="emesso"].attivo{border-color:var(--amber); background:var(--amber-soft)}
  .mod-btn:focus-visible{outline:2px solid var(--amber); outline-offset:2px}

  .display-riga{display:flex; gap:12px; margin-bottom:14px}
  .display{
    flex:1; min-height:118px; background:var(--surface); border:1px solid var(--linea);
    border-radius:16px; display:flex; flex-direction:column; align-items:center; justify-content:center;
  }
  .display .lbl{font-size:11px; letter-spacing:.18em; color:var(--muto);
    text-transform:uppercase; margin-bottom:2px}
  .display .num{font-family:"Space Mono",monospace; font-weight:700; font-size:64px;
    line-height:1; color:var(--testo)}
  .display .num.vuoto{color:var(--normale-dot)}
  .conferma{
    width:118px; flex:none; border:none; border-radius:16px; cursor:pointer;
    background:var(--rosso); color:#fff; font-family:"Inter",sans-serif; font-weight:700;
    font-size:15px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px;
    transition:transform .08s, opacity .15s;
  }
  .conferma .segno{font-size:30px; line-height:1}
  .conferma:active{transform:scale(.97)}
  .conferma:disabled{opacity:.35; cursor:default}
  .conferma:focus-visible{outline:2px solid #fff; outline-offset:2px}

  .tasti{display:grid; grid-template-columns:repeat(3,1fr); gap:12px}
  .tasto{
    min-height:70px; background:var(--surface); border:1px solid var(--linea);
    border-radius:16px; color:var(--testo); font-family:"Space Mono",monospace;
    font-weight:700; font-size:28px; cursor:pointer; transition:transform .08s, background .15s;
  }
  .tasto:hover{background:var(--surface-hi)}
  .tasto:active{transform:scale(.95)}
  .tasto:focus-visible{outline:2px solid var(--amber); outline-offset:2px}
  .tasto.canc{font-size:24px; color:var(--muto)}

  .feedback{min-height:22px; text-align:center; margin-top:16px; font-size:14.5px;
    font-weight:500; color:var(--muto)}
  .feedback.errore{color:var(--rosso)}
  .feedback.ok-emesso{color:var(--amber)}
  .feedback.ok-normale{color:var(--testo)}
  .feedback.ok-incassato{color:var(--verde)}

  /* ---------- Vista TAVOLI (griglia) ---------- */
  .legenda-barra{display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:16px}
  .legenda{display:flex; gap:9px; flex-wrap:wrap; margin-right:auto}
  .chip{display:flex; align-items:center; gap:8px; background:var(--surface);
    border:1px solid var(--linea); border-radius:999px; padding:7px 13px 7px 11px;
    font-size:13px; white-space:nowrap}
  .chip .punto{width:10px; height:10px; border-radius:3px; flex:none}
  .chip .conta{font-family:"Space Mono",monospace; font-weight:700; min-width:1.2em; text-align:right}
  .punto.normale{background:var(--normale-dot)}
  .punto.emesso{background:var(--amber)}
  .punto.incassato{background:var(--verde)}

  .griglia{display:grid; gap:12px; grid-template-columns:repeat(auto-fill, minmax(112px, 1fr))}
  .tavolo{
    position:relative; overflow:hidden; cursor:pointer;
    min-height:96px; padding:16px 12px 12px;
    display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px;
    background:var(--surface); border:1px solid var(--linea); border-radius:14px;
    color:var(--testo); font-family:inherit;
    transition:transform .08s, background .18s, border-color .18s;
  }
  .tavolo::before{content:""; position:absolute; top:0; left:0; right:0; height:5px;
    background:var(--normale-dot); transition:background .18s}
  .tavolo:active{transform:scale(.96)}
  .tavolo:focus-visible{outline:2px solid var(--amber); outline-offset:2px}
  .numero{font-family:"Space Mono",monospace; font-weight:700; font-size:30px; line-height:1}
  .etichetta{font-size:11px; letter-spacing:.04em; color:var(--muto);
    text-transform:uppercase; text-align:center; min-height:1.2em}
  .tavolo.stato-emesso{background:var(--amber-soft); border-color:rgba(245,166,35,.5)}
  .tavolo.stato-emesso::before{background:var(--amber)}
  .tavolo.stato-emesso .etichetta{color:var(--amber)}
  .tavolo.stato-incassato{background:var(--verde-soft); border-color:rgba(39,194,110,.5)}
  .tavolo.stato-incassato::before{background:var(--verde)}
  .tavolo.stato-incassato .etichetta{color:var(--verde)}
  .tavolo.pulsa{animation:flash .6s ease}
  @keyframes flash{0%{box-shadow:0 0 0 0 rgba(245,245,242,.35)}
    100%{box-shadow:0 0 0 8px rgba(245,245,242,0)}}

  @media (max-width:560px){
    .brand{margin-right:0}
    .nav-tabs{order:3; width:100%}
    .nav-tab{flex:1; text-align:center}
    .azioni{margin-left:auto}
    .griglia{grid-template-columns:repeat(auto-fill, minmax(88px, 1fr)); gap:9px}
    .numero{font-size:26px}
    .display .num{font-size:54px}
  }
  @media (prefers-reduced-motion:reduce){
    *{animation:none !important; transition:none !important}
  }
</style>
</head>
<body>
  <header>
    <div class="barra">
      <div class="brand">
        <div class="barcode" aria-hidden="true"></div>
        <div class="titolo">
          <span class="wordmark">BARCODE</span>
          <span class="eyebrow">Gestione tavoli</span>
        </div>
      </div>

      <nav class="nav-tabs">
        <button class="nav-tab" type="button" data-vista="tastierino">Tastierino</button>
        <button class="nav-tab" type="button" data-vista="tavoli">Tavoli</button>
      </nav>

      <div class="azioni">
        <div class="stato-rete" id="stato-rete" title="Connessione al server">
          <span class="led"></span><span id="testo-rete">In linea</span>
        </div>
        <a class="btn" href="/logout">Esci</a>
      </div>
    </div>
  </header>

  <main>
    <!-- ============ TASTIERINO ============ -->
    <section id="vista-tastierino" class="tastierino">
      <div class="modalita">
        <button class="mod-btn attivo" type="button" data-mod="emesso">
          <span class="pallino"></span>Scontrino emesso
        </button>
        <button class="mod-btn" type="button" data-mod="normale">
          <span class="pallino"></span>Normale
        </button>
      </div>

      <div class="display-riga">
        <div class="display">
          <span class="lbl">Tavolo n°</span>
          <span class="num vuoto" id="display-num">—</span>
        </div>
        <button class="conferma" id="btn-conferma" type="button" disabled>
          <span class="segno">✓</span>Conferma
        </button>
      </div>

      <div class="tasti" id="tasti">
        <button class="tasto" type="button" data-cifra="1">1</button>
        <button class="tasto" type="button" data-cifra="2">2</button>
        <button class="tasto" type="button" data-cifra="3">3</button>
        <button class="tasto" type="button" data-cifra="4">4</button>
        <button class="tasto" type="button" data-cifra="5">5</button>
        <button class="tasto" type="button" data-cifra="6">6</button>
        <button class="tasto" type="button" data-cifra="7">7</button>
        <button class="tasto" type="button" data-cifra="8">8</button>
        <button class="tasto" type="button" data-cifra="9">9</button>
        <button class="tasto canc" type="button" id="tasto-canc">⌫</button>
        <button class="tasto" type="button" data-cifra="0">0</button>
        <button class="tasto canc" type="button" id="tasto-azzera">C</button>
      </div>

      <p class="feedback" id="feedback"></p>
    </section>

    <!-- ============ GRIGLIA TAVOLI ============ -->
    <section id="vista-tavoli" style="display:none">
      <div class="legenda-barra">
        <div class="legenda" aria-hidden="true">
          <div class="chip"><span class="punto normale"></span>Normale<span class="conta" id="conta-normale">0</span></div>
          <div class="chip"><span class="punto emesso"></span>Scontrino emesso<span class="conta" id="conta-emessi">0</span></div>
          <div class="chip"><span class="punto incassato"></span>Incassato<span class="conta" id="conta-incassati">0</span></div>
        </div>
        <button class="btn" id="btn-reset">Azzera tutti</button>
      </div>
      <div class="griglia" id="griglia"></div>
    </section>
  </main>

<script>
  const NUM_TAVOLI = __NUM_TAVOLI__;
  const STATI = ["normale", "emesso", "incassato"];
  const ETICHETTE = {normale:"Normale", emesso:"Scontrino emesso", incassato:"Incassato"};

  const griglia = document.getElementById("griglia");
  const statoReteEl = document.getElementById("stato-rete");
  const testoReteEl = document.getElementById("testo-rete");

  let statoCorrente = {};      // id -> stato attualmente mostrato
  let inVolo = new Set();      // id con richiesta POST in corso
  let primaCarica = true;

  /* ---------- Griglia (comportamento invariato) ---------- */
  function creaGriglia(){
    for(let i = 1; i <= NUM_TAVOLI; i++){
      const btn = document.createElement("button");
      btn.className = "tavolo stato-normale";
      btn.type = "button";
      btn.dataset.id = i;
      btn.setAttribute("aria-label", "Tavolo " + i + ": Normale");
      btn.innerHTML = '<span class="numero">' + i + '</span>'
                    + '<span class="etichetta">Normale</span>';
      btn.addEventListener("click", () => onTap(i));
      griglia.appendChild(btn);
      statoCorrente[i] = "normale";
    }
  }

  function applicaStato(id, stato){
    const btn = griglia.querySelector('[data-id="' + id + '"]');
    if(!btn) return;
    btn.classList.remove("stato-normale", "stato-emesso", "stato-incassato");
    btn.classList.add("stato-" + stato);
    btn.querySelector(".etichetta").textContent = ETICHETTE[stato];
    btn.setAttribute("aria-label", "Tavolo " + id + ": " + ETICHETTE[stato]);
  }

  function pulsa(id){
    const btn = griglia.querySelector('[data-id="' + id + '"]');
    if(!btn) return;
    btn.classList.add("pulsa");
    setTimeout(() => btn.classList.remove("pulsa"), 600);
  }

  function aggiornaConteggi(){
    let e = 0, inc = 0;
    for(let i = 1; i <= NUM_TAVOLI; i++){
      const s = statoCorrente[i] || "normale";
      if(s === "emesso") e++;
      else if(s === "incassato") inc++;
    }
    document.getElementById("conta-emessi").textContent = e;
    document.getElementById("conta-incassati").textContent = inc;
    document.getElementById("conta-normale").textContent = NUM_TAVOLI - e - inc;
  }

  function render(nuovo){
    for(let i = 1; i <= NUM_TAVOLI; i++){
      if(inVolo.has(i)) continue;
      const ns = STATI.includes(nuovo[i]) ? nuovo[i] : "normale";
      const vs = statoCorrente[i] || "normale";
      if(ns !== vs){
        applicaStato(i, ns);
        if(!primaCarica) pulsa(i);
      }
      statoCorrente[i] = ns;
    }
    primaCarica = false;
    aggiornaConteggi();
  }

  function segnaRete(ok){
    statoReteEl.classList.toggle("offline", !ok);
    testoReteEl.textContent = ok ? "In linea" : "Riconnessione…";
  }

  async function caricaStato(){
    try{
      const r = await fetch("/api/state", {headers:{"Accept":"application/json"}});
      if(r.status === 401){ window.location.href = "/login"; return; }
      if(!r.ok) throw new Error("stato " + r.status);
      render(await r.json());
      segnaRete(true);
    }catch(err){ segnaRete(false); }
  }

  // Tap sulla griglia: cicla lo stato (nessun corpo nella richiesta)
  async function onTap(id){
    const attuale = statoCorrente[id] || "normale";
    const prossimo = STATI[(STATI.indexOf(attuale) + 1) % STATI.length];
    statoCorrente[id] = prossimo;
    applicaStato(id, prossimo);
    aggiornaConteggi();
    inVolo.add(id);
    try{
      const r = await fetch("/api/table/" + id, {method:"POST", headers:{"Accept":"application/json"}});
      if(r.status === 401){ window.location.href = "/login"; return; }
      if(!r.ok) throw new Error("post " + r.status);
      const dati = await r.json();
      statoCorrente[id] = dati.stato;
      applicaStato(id, dati.stato);
      aggiornaConteggi();
      segnaRete(true);
    }catch(err){ segnaRete(false); }
    finally{ inVolo.delete(id); }
  }

  async function azzeraTutti(){
    if(!confirm("Azzerare tutti i " + NUM_TAVOLI + " tavoli? Torneranno tutti a «Normale».")) return;
    try{
      const r = await fetch("/api/reset", {method:"POST", headers:{"Accept":"application/json"}});
      if(r.status === 401){ window.location.href = "/login"; return; }
      if(!r.ok) throw new Error("reset " + r.status);
      render(await r.json());
      segnaRete(true);
    }catch(err){ segnaRete(false); }
  }
  document.getElementById("btn-reset").addEventListener("click", azzeraTutti);

  /* ---------- Tastierino ---------- */
  let modalita = "emesso";
  let buffer = "";

  const elNum = document.getElementById("display-num");
  const elConferma = document.getElementById("btn-conferma");
  const elFeedback = document.getElementById("feedback");

  function aggiornaDisplay(){
    if(buffer === ""){
      elNum.textContent = "—";
      elNum.classList.add("vuoto");
      elConferma.disabled = true;
    }else{
      elNum.textContent = buffer;
      elNum.classList.remove("vuoto");
      elConferma.disabled = false;
    }
  }

  function premiCifra(c){
    if(buffer.length >= 3) return;
    if(buffer === "" && c === "0") return;   // niente zero iniziale
    buffer += c;
    elFeedback.textContent = "";
    elFeedback.className = "feedback";
    aggiornaDisplay();
  }

  function cancellaUltima(){
    buffer = buffer.slice(0, -1);
    aggiornaDisplay();
  }

  function azzeraBuffer(){
    buffer = "";
    elFeedback.textContent = "";
    elFeedback.className = "feedback";
    aggiornaDisplay();
  }

  function selezionaModalita(m){
    modalita = m;
    document.querySelectorAll(".mod-btn").forEach(b =>
      b.classList.toggle("attivo", b.dataset.mod === m));
  }

  async function conferma(){
    const n = parseInt(buffer, 10);
    if(!n || n < 1 || n > NUM_TAVOLI){
      elFeedback.textContent = "Tavolo non valido (1–" + NUM_TAVOLI + ")";
      elFeedback.className = "feedback errore";
      return;
    }
    try{
      const r = await fetch("/api/table/" + n, {
        method:"POST",
        headers:{"Content-Type":"application/json", "Accept":"application/json"},
        body: JSON.stringify({stato: modalita})
      });
      if(r.status === 401){ window.location.href = "/login"; return; }
      if(!r.ok) throw new Error("post " + r.status);
      const dati = await r.json();
      statoCorrente[n] = dati.stato;
      applicaStato(n, dati.stato);     // aggiorna subito anche la cella nella griglia
      aggiornaConteggi();
      azzeraBuffer();                  // pulisce il numero per il prossimo tavolo
      elFeedback.textContent = "Tavolo " + n + " → " + ETICHETTE[dati.stato];
      elFeedback.className = "feedback ok-" + dati.stato;
      segnaRete(true);
    }catch(err){
      elFeedback.textContent = "Errore di rete, riprova";
      elFeedback.className = "feedback errore";
      segnaRete(false);
    }
  }

  // Eventi tastierino
  document.querySelectorAll(".tasto[data-cifra]").forEach(t =>
    t.addEventListener("click", () => premiCifra(t.dataset.cifra)));
  document.getElementById("tasto-canc").addEventListener("click", cancellaUltima);
  document.getElementById("tasto-azzera").addEventListener("click", azzeraBuffer);
  document.querySelectorAll(".mod-btn").forEach(b =>
    b.addEventListener("click", () => selezionaModalita(b.dataset.mod)));
  elConferma.addEventListener("click", conferma);

  // Tastiera fisica (utile con iPad + tastiera)
  document.addEventListener("keydown", (e) => {
    if(document.getElementById("vista-tastierino").style.display === "none") return;
    if(e.key >= "0" && e.key <= "9"){ premiCifra(e.key); }
    else if(e.key === "Backspace"){ e.preventDefault(); cancellaUltima(); }
    else if(e.key === "Enter"){ e.preventDefault(); if(!elConferma.disabled) conferma(); }
  });

  /* ---------- Navigazione fra le viste ---------- */
  function mostraVista(v){
    document.getElementById("vista-tastierino").style.display = (v === "tastierino") ? "block" : "none";
    document.getElementById("vista-tavoli").style.display = (v === "tavoli") ? "block" : "none";
    document.querySelectorAll(".nav-tab").forEach(t =>
      t.classList.toggle("attivo", t.dataset.vista === v));
  }
  document.querySelectorAll(".nav-tab").forEach(t =>
    t.addEventListener("click", () => mostraVista(t.dataset.vista)));

  /* ---------- Avvio ---------- */
  creaGriglia();
  aggiornaDisplay();
  selezionaModalita("emesso");
  mostraVista("tastierino");        // schermata iniziale: il tastierino
  caricaStato();
  setInterval(caricaStato, 4000);   // sincronizza fra i dispositivi ogni 4 secondi
</script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
