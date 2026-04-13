import discord
from discord.ext import commands
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import threading
import os
import json
import secrets
from functools import wraps

# ================= CONFIGURACIÓN =================
TOKEN = os.getenv("TOKEN")  # Pon tu token aquí si no usas variables de entorno
WEB_PASSWORD = "admin123"  # CAMBIA ESTO por tu contraseña segura

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "antialts": os.path.join(BASE_DIR, "antialts_config.json"),
    "antibots": os.path.join(BASE_DIR, "antibots.json"),
    "antiflood": os.path.join(BASE_DIR, "antiflood.json"),
    "antilinks": os.path.join(BASE_DIR, "antilinks.json"),
    "logs": os.path.join(BASE_DIR, "logs_config.json"),
    "verification": os.path.join(BASE_DIR, "verification.json")
}

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

COLOR_HEX = "#0A3D62"
COLOR_BG = "#052035"
COLOR_CARD = "#082F49"

# ================= HELPERS JSON =================
def load_json(key):
    path = FILES.get(key)
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(key, data):
    path = FILES.get(key)
    if not path:
        return False
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except:
        return False

# ================= DECORADOR DE SEGURIDAD =================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ================= HTML DE LA DASHBOARD =================
HTML_DASHBOARD = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ModdyBot Dashboard</title>
    <style>
        :root {{ --bg: {COLOR_BG}; --card: {COLOR_CARD}; --accent: {COLOR_HEX}; --text: #ffffff; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); margin: 0; }}
        .navbar {{ background: var(--card); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--accent); }}
        .navbar h1 {{ margin: 0; font-size: 1.5rem; color: var(--accent); }}
        .container {{ max-width: 1200px; margin: 30px auto; padding: 0 20px; }}
        
        .server-selector {{ background: var(--card); padding: 20px; border-radius: 10px; margin-bottom: 30px; border: 1px solid var(--accent); display: flex; gap: 15px; align-items: center; }}
        .server-selector select {{ padding: 10px; border-radius: 6px; border: 1px solid var(--accent); background: var(--bg); color: var(--text); font-size: 1rem; min-width: 300px; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .stat-card {{ background: var(--card); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid var(--accent); }}
        .stat-card h3 {{ margin: 0; font-size: 2.5rem; color: var(--accent); }}
        
        .module {{ background: var(--card); border-radius: 12px; margin-bottom: 30px; overflow: hidden; border: 1px solid var(--accent); }}
        .module-header {{ background: rgba(0,0,0,0.2); padding: 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }}
        .module-header h2 {{ margin: 0; color: var(--accent); }}
        .module-content {{ padding: 25px; display: none; }}
        .module.active .module-content {{ display: block; }}
        
        .form-group {{ margin-bottom: 20px; }}
        .form-group label {{ display: block; margin-bottom: 8px; font-weight: bold; color: var(--accent); }}
        .form-control {{ width: 100%; padding: 10px; border-radius: 6px; border: 1px solid var(--accent); background: var(--bg); color: var(--text); font-size: 1rem; }}
        .toggle-switch {{ position: relative; display: inline-block; width: 60px; height: 34px; }}
        .toggle-switch input {{ opacity: 0; width: 0; height: 0; }}
        .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 34px; }}
        .slider:before {{ position: absolute; content: ""; height: 26px; width: 26px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; }}
        input:checked + .slider {{ background-color: var(--accent); }}
        input:checked + .slider:before {{ transform: translateX(26px); }}
        
        .btn {{ background: var(--accent); color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-size: 1rem; font-weight: bold; transition: transform 0.2s; }}
        .btn:hover {{ transform: scale(1.05); }}
        .btn-secondary {{ background: #5865F2; }}
        
        .panel-list {{ list-style: none; padding: 0; }}
        .panel-item {{ background: rgba(0,0,0,0.2); padding: 15px; margin-bottom: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; }}
        
        footer {{ text-align: center; margin-top: 60px; padding: 20px; opacity: 0.5; }}
        .alert {{ padding: 15px; border-radius: 6px; margin-bottom: 20px; display: none; }}
        .alert-success {{ background: #43b581; color: white; }}
        .alert-error {{ background: #f04747; color: white; }}
    </style>
</head>
<body>
    <div class="navbar">
        <h1>🛡️ ModdyBot Dashboard</h1>
        <a href="/logout" class="btn btn-secondary" style="text-decoration:none; font-size:0.9rem;">Cerrar Sesión</a>
    </div>

    <div class="container">
        <!-- Selector de Servidor -->
        <div class="server-selector">
            <label for="guild-select" style="font-weight:bold; color:var(--accent);">Servidor:</label>
            <select id="guild-select" class="form-control" onchange="loadConfig()"></select>
        </div>

        <!-- Estadísticas -->
        <div class="stats-grid">
            <div class="stat-card"><h3 id="stat-guilds">0</h3><p>Servidores</p></div>
            <div class="stat-card"><h3 id="stat-users">0</h3><p>Usuarios</p></div>
            <div class="stat-card"><h3 id="stat-latency">0</h3><p>Latencia (ms)</p></div>
        </div>

        <!-- Alertas -->
        <div id="alert-box" class="alert"></div>

        <!-- 1. ANTI-ALTS -->
        <div class="module">
            <div class="module-header" onclick="toggleModule(this)"><h2>👶 Anti-Alts</h2><span>▼</span></div>
            <div class="module-content">
                <div class="form-group"><label>Días Mínimos</label><input type="number" id="antialts-days" class="form-control"></div>
                <div class="form-group"><label>Canal de Logs</label><select id="antialts-logs" class="form-control channel-select"></select></div>
                <button class="btn" onclick="saveConfig('antialts')">Guardar Cambios</button>
            </div>
        </div>

        <!-- 2. ANTI-BOTS -->
        <div class="module">
            <div class="module-header" onclick="toggleModule(this)"><h2>🤖 Anti-Bots</h2><span>▼</span></div>
            <div class="module-content">
                <div class="form-group"><label>Estado</label><label class="toggle-switch"><input type="checkbox" id="antibots-enabled"><span class="slider"></span></label></div>
                <div class="form-group"><label>Canal de Logs</label><select id="antibots-logs" class="form-control channel-select"></select></div>
                <button class="btn" onclick="saveConfig('antibots')">Guardar Cambios</button>
            </div>
        </div>

        <!-- 3. ANTI-FLOOD -->
        <div class="module">
            <div class="module-header" onclick="toggleModule(this)"><h2>🌊 Anti-Flood</h2><span>▼</span></div>
            <div class="module-content">
                <div class="form-group"><label>Estado</label><label class="toggle-switch"><input type="checkbox" id="antiflood-enabled"><span class="slider"></span></label></div>
                <div class="form-group"><label>Nivel</label><select id="antiflood-level" class="form-control"><option value="bajo">Bajo</option><option value="medio">Medio</option><option value="alto">Alto</option></select></div>
                <div class="form-group"><label>Acción</label><select id="antiflood-action" class="form-control"><option value="mute">Mute</option><option value="kick">Kick</option><option value="ban">Ban</option></select></div>
                <div class="form-group"><label>Tiempo de Mute (segundos)</label><input type="number" id="antiflood-mute-time" class="form-control"></div>
                <div class="form-group"><label>Canal de Logs</label><select id="antiflood-logs" class="form-control channel-select"></select></div>
                <button class="btn" onclick="saveConfig('antiflood')">Guardar Cambios</button>
            </div>
        </div>

        <!-- 4. ANTI-LINKS -->
        <div class="module">
            <div class="module-header" onclick="toggleModule(this)"><h2>🔗 Anti-Links</h2><span>▼</span></div>
            <div class="module-content">
                <div class="form-group"><label>Estado</label><label class="toggle-switch"><input type="checkbox" id="antilinks-enabled"><span class="slider"></span></label></div>
                <div class="form-group"><label>Acción</label><select id="antilinks-action" class="form-control"><option value="mute">Mute</option><option value="kick">Kick</option><option value="ban">Ban</option></select></div>
                <div class="form-group"><label>Permitir Invites</label><label class="toggle-switch"><input type="checkbox" id="antilinks-allow-invites"><span class="slider"></span></label></div>
                <div class="form-group"><label>Canal de Logs</label><select id="antilinks-logs" class="form-control channel-select"></select></div>
                <button class="btn" onclick="saveConfig('antilinks')">Guardar Cambios</button>
            </div>
        </div>

        <!-- 5. ULTRA LOGS -->
        <div class="module">
            <div class="module-header" onclick="toggleModule(this)"><h2>📝 Ultra Logs</h2><span>▼</span></div>
            <div class="module-content">
                <div class="form-group"><label>Estado General</label><label class="toggle-switch"><input type="checkbox" id="logs-enabled"><span class="slider"></span></label></div>
                <div class="form-group"><label>Canal de Logs</label><select id="logs-channel" class="form-control channel-select"></select></div>
                <div class="form-group"><label>Categorías</label>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                        <label><input type="checkbox" id="logs-joins"> Joins/Leaves</label>
                        <label><input type="checkbox" id="logs-roles"> Roles</label>
                        <label><input type="checkbox" id="logs-canales"> Canales</label>
                        <label><input type="checkbox" id="logs-mensajes"> Mensajes</label>
                        <label><input type="checkbox" id="logs-servidor"> Servidor</label>
                    </div>
                </div>
                <button class="btn" onclick="saveConfig('logs')">Guardar Cambios</button>
            </div>
        </div>

        <!-- 6. VERIFICACIÓN -->
        <div class="module">
            <div class="module-header" onclick="toggleModule(this)"><h2>✅ Verificación</h2><span>▼</span></div>
            <div class="module-content">
                <h3>Paneles Existentes</h3>
                <ul id="verification-list" class="panel-list"></ul>
                <hr style="border-color:var(--accent); opacity:0.3; margin:20px 0;">
                <h3>Enviar Panel</h3>
                <div class="form-group"><label>Seleccionar Panel</label><select id="verify-panel-select" class="form-control"></select></div>
                <div class="form-group"><label>Canal de Destino</label><select id="verify-channel-dest" class="form-control channel-select"></select></div>
                <button class="btn" onclick="sendVerificationPanel()">Enviar Panel</button>
            </div>
        </div>
    </div>

    <footer>ModdyBot Dashboard • Local</footer>

    <script>
        let currentGuildId = null;
        let allChannels = [];

        function toggleModule(header) {{ header.parentElement.classList.toggle('active'); }}

        function showAlert(msg, type) {{
            const box = document.getElementById('alert-box');
            box.className = 'alert alert-' + type;
            box.innerText = msg;
            box.style.display = 'block';
            setTimeout(() => box.style.display = 'none', 3000);
        }}

        async function loadDashboard() {{
            const res = await fetch('/api/init');
            const data = await res.json();
            
            const select = document.getElementById('guild-select');
            select.innerHTML = '';
            data.guilds.forEach(g => {{
                const opt = document.createElement('option');
                opt.value = g.id;
                opt.innerText = g.name;
                select.appendChild(opt);
            }});
            
            if (data.guilds.length > 0) {{
                currentGuildId = data.guilds[0].id;
                loadConfig();
            }}
            
            document.getElementById('stat-guilds').innerText = data.guilds.length;
            document.getElementById('stat-users').innerText = data.total_users;
            document.getElementById('stat-latency').innerText = data.latency;
        }}

        async function loadConfig() {{
            currentGuildId = document.getElementById('guild-select').value;
            const res = await fetch('/api/config?guild=' + currentGuildId);
            const data = await res.json();
            
            allChannels = data.channels || [];
            const channelSelects = document.querySelectorAll('.channel-select');
            channelSelects.forEach(sel => {{
                sel.innerHTML = '<option value="">-- Seleccionar --</option>';
                allChannels.forEach(ch => {{
                    const opt = document.createElement('option');
                    opt.value = ch.id;
                    opt.innerText = '#' + ch.name;
                    sel.appendChild(opt);
                }});
            }});

            // Anti-Alts
            const aa = data.antialts[currentGuildId] || {{}};
            document.getElementById('antialts-days').value = aa.dias || 7;
            document.getElementById('antialts-logs').value = aa.logs || '';

            // Anti-Bots
            const ab = data.antibots[currentGuildId] || {{}};
            document.getElementById('antibots-enabled').checked = ab.enabled || false;
            document.getElementById('antibots-logs').value = ab.log_channel || '';

            // Anti-Flood
            const af = data.antiflood[currentGuildId] || {{}};
            document.getElementById('antiflood-enabled').checked = af.enabled || false;
            document.getElementById('antiflood-level').value = af.nivel || 'medio';
            document.getElementById('antiflood-action').value = af.accion || 'mute';
            document.getElementById('antiflood-mute-time').value = af.mute_time || 600;
            document.getElementById('antiflood-logs').value = af.log_channel || '';

            // Anti-Links
            const al = data.antilinks[currentGuildId] || {{}};
            document.getElementById('antilinks-enabled').checked = al.enabled || false;
            document.getElementById('antilinks-action').value = al.accion || 'mute';
            document.getElementById('antilinks-allow-invites').checked = al.allow_invites || false;
            document.getElementById('antilinks-logs').value = al.log_channel || '';

            // Logs
            const lg = data.logs[currentGuildId] || {{}};
            document.getElementById('logs-enabled').checked = lg.enabled || false;
            document.getElementById('logs-channel').value = lg.channel || '';
            const cats = lg.categories || {{}};
            document.getElementById('logs-joins').checked = cats.joins !== false;
            document.getElementById('logs-roles').checked = cats.roles !== false;
            document.getElementById('logs-canales').checked = cats.canales !== false;
            document.getElementById('logs-mensajes').checked = cats.mensajes !== false;
            document.getElementById('logs-servidor').checked = cats.servidor !== false;

            // Verificación
            const ver = data.verification[currentGuildId] || {{}};
            const list = document.getElementById('verification-list');
            const panelSelect = document.getElementById('verify-panel-select');
            list.innerHTML = '';
            panelSelect.innerHTML = '<option value="">-- Seleccionar --</option>';
            
            if (Object.keys(ver).length === 0) {{
                list.innerHTML = '<li>No hay paneles creados. Usa /verificacion en Discord.</li>';
            }} else {{
                for (const [pid, cfg] of Object.entries(ver)) {{
                    list.innerHTML += `<li class="panel-item"><span><strong>ID:</strong> ${{pid}} | <strong>Tipo:</strong> ${{cfg.tipo}} | <strong>Rol:</strong> ${{cfg.rol_dar ? 'Sí' : 'No'}}</span></li>`;
                    panelSelect.innerHTML += `<option value="${{pid}}">$${{pid}}</option>`;
                }}
            }}
        }}

        async function saveConfig(module) {{
            let payload = {{ guild_id: currentGuildId, module: module }};
            if (module === 'antialts') {{
                payload.data = {{ dias: parseInt(document.getElementById('antialts-days').value), logs: document.getElementById('antialts-logs').value }};
            }} else if (module === 'antibots') {{
                payload.data = {{ enabled: document.getElementById('antibots-enabled').checked, log_channel: document.getElementById('antibots-logs').value }};
            }} else if (module === 'antiflood') {{
                payload.data = {{ enabled: document.getElementById('antiflood-enabled').checked, nivel: document.getElementById('antiflood-level').value, accion: document.getElementById('antiflood-action').value, mute_time: parseInt(document.getElementById('antiflood-mute-time').value), log_channel: document.getElementById('antiflood-logs').value }};
            }} else if (module === 'antilinks') {{
                payload.data = {{ enabled: document.getElementById('antilinks-enabled').checked, accion: document.getElementById('antilinks-action').value, allow_invites: document.getElementById('antilinks-allow-invites').checked, log_channel: document.getElementById('antilinks-logs').value }};
            }} else if (module === 'logs') {{
                payload.data = {{ enabled: document.getElementById('logs-enabled').checked, channel: document.getElementById('logs-channel').value, categories: {{ joins: document.getElementById('logs-joins').checked, roles: document.getElementById('logs-roles').checked, canales: document.getElementById('logs-canales').checked, mensajes: document.getElementById('logs-mensajes').checked, servidor: document.getElementById('logs-servidor').checked }} }};
            }}
            
            const res = await fetch('/api/save', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(payload) }});
            const result = await res.json();
            showAlert(result.message, result.success ? 'success' : 'error');
        }}

        async function sendVerificationPanel() {{
            const panelId = document.getElementById('verify-panel-select').value;
            const channelId = document.getElementById('verify-channel-dest').value;
            if (!panelId || !channelId) return showAlert('Selecciona panel y canal', 'error');
            
            const res = await fetch('/api/send-panel', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ guild_id: currentGuildId, panel_id: panelId, channel_id: channelId }}) }});
            const result = await res.json();
            showAlert(result.message, result.success ? 'success' : 'error');
        }}

        document.getElementById('guild-select').addEventListener('change', loadConfig);
        window.onload = loadDashboard;
    </script>
</body>
</html>
"""

# ================= RUTAS WEB =================
@app.route('/')
@login_required
def dashboard():
    return render_template_string(HTML_DASHBOARD)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return "Contraseña incorrecta", 401
    return """
    <html><head><style>body{{background:#052035;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}}form{{background:#082F49;padding:40px;border-radius:10px;border:2px solid #0A3D62;text-align:center;}}input{{padding:10px;margin:10px 0;border-radius:5px;border:none;width:100%;}}button{{background:#0A3D62;color:white;padding:10px 20px;border:none;border-radius:5px;cursor:pointer;font-weight:bold;}}</style></head>
    <body><form method="post"><h2>🔐 ModdyBot Login</h2><input type="password" name="password" placeholder="Contraseña"><button type="submit">Entrar</button></form></body></html>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/init')
@login_required
def api_init():
    guilds = []
    total_users = 0
    for g in bot.guilds:
        guilds.append({{"id": str(g.id), "name": g.name}})
        total_users += g.member_count or 0
    return jsonify({{
        "guilds": guilds,
        "total_users": total_users,
        "latency": round(bot.latency * 1000, 2) if bot.latency else 0
    }})

@app.route('/api/config')
@login_required
def api_config():
    guild_id = request.args.get('guild')
    data = {{}}
    for key in FILES.keys():
        data[key] = load_json(key)
    
    guild = bot.get_guild(int(guild_id))
    channels = []
    if guild:
        for ch in guild.text_channels:
            channels.append({{"id": str(ch.id), "name": ch.name}})
    
    return jsonify({{**data, "channels": channels}})

@app.route('/api/save', methods=['POST'])
@login_required
def api_save():
    req = request.json
    module = req.get('module')
    guild_id = req.get('guild_id')
    new_data = req.get('data', {{}})
    
    current = load_json(module)
    
    if module == 'antialts':
        current[guild_id] = new_data
    elif module == 'antibots':
        if guild_id not in current: current[guild_id] = {{}}
        current[guild_id].update(new_data)
    elif module == 'antiflood':
        if guild_id not in current: current[guild_id] = {{}}
        current[guild_id].update(new_data)
    elif module == 'antilinks':
        if guild_id not in current: current[guild_id] = {{}}
        current[guild_id].update(new_data)
    elif module == 'logs':
        if guild_id not in current: current[guild_id] = {{}}
        current[guild_id].update(new_data)
    
    success = save_json(module, current)
    return jsonify({{"success": success, "message": "Guardado correctamente" if success else "Error al guardar"}})

@app.route('/api/send-panel', methods=['POST'])
@login_required
def api_send_panel():
    req = request.json
    guild_id = req.get('guild_id')
    panel_id = req.get('panel_id')
    channel_id = req.get('channel_id')
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({{"success": False, "message": "Servidor no encontrado"}})
    
    channel = guild.get_channel(int(channel_id))
    if not channel:
        return jsonify({{"success": False, "message": "Canal no encontrado"}})
    
    # Reconstruir embed y botón (simplificado)
    embed = discord.Embed(
        title="<:moderacion:1483506627649994812> ModdyBot — Verificación",
        description="Bienvenido al sistema de protección avanzada de **ModdyBot**.

Pulsa el botón para verificarte.",
        color=discord.Color(0x0A3D62)
    )
    embed.set_image(url="https://raw.githubusercontent.com/lildrakk/ModdyBot-web/eb6b1cb04336b0929a83cacad3b6834d11cedf8c/standard-3.gif")
    
    class VerifyButton(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(discord.ui.Button(label="Verificarme", emoji="✅", style=discord.ButtonStyle.success, custom_id=f"verify_{panel_id}"))
    
    try:
        threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(channel.send(embed=embed, view=VerifyButton()), bot.loop)).start()
        return jsonify({{"success": True, "message": "Panel enviado correctamente"}})
    except Exception as e:
        return jsonify({{"success": False, "message": f"Error: {{str(e)}}"}})

# ================= RUN =================
def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

@bot.event
async def on_ready():
    print(f"✅ Dashboard conectada como {bot.user}")
    print(f"🌐 Web disponible en: http://localhost:{PORT}")
    print(f"🔐 Contraseña: {WEB_PASSWORD}")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(TOKEN)
