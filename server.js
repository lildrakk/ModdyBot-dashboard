require('dotenv').config();
const express = require('express');
const session = require('express-session');
const passport = require('passport');
const DiscordStrategy = require('passport-discord').Strategy;
const axios = require('axios');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const BOT_URL = process.env.BOT_URL;
const BOT_API_KEY = process.env.BOT_API_KEY;
const OWNER_ID = process.env.OWNER_ID;

// =============================================
// JSON HELPERS
// =============================================
const DATA_PATH = path.join(__dirname, 'data');
if (!fs.existsSync(DATA_PATH)) fs.mkdirSync(DATA_PATH, { recursive: true });

function loadJSON(filename) {
  const fp = path.join(DATA_PATH, filename);
  if (!fs.existsSync(fp)) return {};
  try { return JSON.parse(fs.readFileSync(fp, 'utf8')); }
  catch { return {}; }
}

function saveJSON(filename, data) {
  fs.writeFileSync(path.join(DATA_PATH, filename), JSON.stringify(data, null, 4), 'utf8');
}

// =============================================
// NOTIFICAR AL BOT QUE RECARGUE UN MÓDULO
// =============================================
async function notifyBot(module, guildId) {
  if (!BOT_URL || !BOT_API_KEY) return;
  try {
    await axios.post(`${BOT_URL}/reload`, { module, guildId }, {
      headers: { 'x-api-key': BOT_API_KEY },
      timeout: 5000
    });
  } catch (e) {
    console.warn(`[WARN] No se pudo notificar al bot (${module}): ${e.message}`);
  }
}

// =============================================
// MIDDLEWARES
// =============================================
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'moddybot_secret_v2',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 1000 * 60 * 60 * 24 }
}));

app.use(passport.initialize());
app.use(passport.session());

// =============================================
// DISCORD OAUTH2
// =============================================
passport.use(new DiscordStrategy({
  clientID: process.env.DISCORD_CLIENT_ID,
  clientSecret: process.env.DISCORD_CLIENT_SECRET,
  callbackURL: process.env.DISCORD_CALLBACK_URL,
  scope: ['identify', 'guilds']
}, (accessToken, refreshToken, profile, done) => {
  return done(null, profile);
}));

passport.serializeUser((user, done) => done(null, user));
passport.deserializeUser((user, done) => done(null, user));

// =============================================
// HELPERS DE PERMISOS
// =============================================

// Comprueba si el usuario es admin en un guild concreto
function isAdminInGuild(user, guildId) {
  if (user.id === OWNER_ID) return true;
  const guild = (user.guilds || []).find(g => g.id === guildId);
  if (!guild) return false;
  const perms = BigInt(guild.permissions);
  const ADMIN = BigInt(0x8);
  const MANAGE_GUILD = BigInt(0x20);
  return (perms & ADMIN) === ADMIN || (perms & MANAGE_GUILD) === MANAGE_GUILD;
}

// Devuelve los guilds donde el usuario es admin
function getAdminGuilds(user) {
  if (!user || !user.guilds) return [];
  if (user.id === OWNER_ID) return user.guilds;
  return user.guilds.filter(g => {
    const perms = BigInt(g.permissions);
    const ADMIN = BigInt(0x8);
    const MANAGE_GUILD = BigInt(0x20);
    return (perms & ADMIN) === ADMIN || (perms & MANAGE_GUILD) === MANAGE_GUILD;
  });
}

// =============================================
// MIDDLEWARES AUTH
// =============================================
function requireLogin(req, res, next) {
  if (!req.isAuthenticated()) return res.redirect('/');
  next();
}

function requireGuildAdmin(req, res, next) {
  if (!req.isAuthenticated()) return res.status(401).json({ error: 'No autenticado' });
  const guildId = req.params.guildId || req.body?.guildId;
  if (!guildId) return res.status(400).json({ error: 'guildId requerido' });
  if (!isAdminInGuild(req.user, guildId)) {
    return res.status(403).json({ error: 'No eres administrador de ese servidor' });
  }
  next();
}

function requireOwner(req, res, next) {
  if (!req.isAuthenticated()) return res.status(401).json({ error: 'No autenticado' });
  if (req.user.id !== OWNER_ID) return res.status(403).json({ error: 'Solo el owner del bot puede hacer esto' });
  next();
}

// =============================================
// RUTAS PÁGINAS
// =============================================
app.get('/', (req, res) => {
  if (req.isAuthenticated()) return res.redirect('/dashboard');
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/dashboard', requireLogin, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});

app.get('/auth/discord', passport.authenticate('discord'));

app.get('/auth/callback',
  passport.authenticate('discord', { failureRedirect: '/' }),
  (req, res) => res.redirect('/dashboard')
);

app.get('/auth/logout', (req, res) => {
  req.logout(() => res.redirect('/'));
});

// =============================================
// API — USUARIO Y SERVERS
// =============================================
app.get('/api/me', requireLogin, (req, res) => {
  const adminGuilds = getAdminGuilds(req.user);
  res.json({
    id: req.user.id,
    username: req.user.username,
    avatar: req.user.avatar,
    isOwner: req.user.id === OWNER_ID,
    guilds: adminGuilds
  });
});

// =============================================
// API — SYNC DESDE EL BOT (bot → dashboard)
// Bot llama a este endpoint cuando cambia algo
// =============================================
function requireBotKey(req, res, next) {
  if (req.headers['x-api-key'] !== BOT_API_KEY) {
    return res.status(401).json({ error: 'API Key inválida' });
  }
  next();
}

const ALLOWED_FILES = [
  'antilinks.json', 'antiflood.json', 'antiping.json',
  'antibots.json', 'antialts_config.json', 'logs_config.json',
  'verification.json', 'dm.json', 'blacklist_servers.json'
];

// Bot envía un JSON actualizado → dashboard lo guarda
app.post('/api/sync/:filename', requireBotKey, (req, res) => {
  const { filename } = req.params;
  if (!ALLOWED_FILES.includes(filename)) return res.status(400).json({ error: 'Archivo no permitido' });
  saveJSON(filename, req.body);
  res.json({ success: true });
});

// Dashboard pide el JSON actual al bot (para tener la última versión)
app.get('/api/sync/:filename', requireBotKey, (req, res) => {
  const { filename } = req.params;
  if (!ALLOWED_FILES.includes(filename)) return res.status(400).json({ error: 'Archivo no permitido' });
  res.json(loadJSON(filename));
});

// =============================================
// API — ANTILINKS
// =============================================
app.get('/api/config/antilinks/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('antilinks.json');
  res.json(data[req.params.guildId] || {
    enabled: false, accion: 'mute', mute_time: 600,
    allow_invites: false, whitelist_users: [], whitelist_roles: [], log_channel: null
  });
});

app.post('/api/config/antilinks/:guildId', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('antilinks.json');
  const gid = req.params.guildId;
  data[gid] = { ...( data[gid] || {}), ...req.body };
  saveJSON('antilinks.json', data);
  await notifyBot('antilinks', gid);
  res.json({ success: true });
});

// =============================================
// API — ANTIFLOOD
// =============================================
app.get('/api/config/antiflood/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('antiflood.json');
  res.json(data[req.params.guildId] || {
    enabled: false, nivel: 'medio', accion: 'mute', mute_time: 600,
    log_channel: null, settings: { interval: 4, max_messages: 5, delete_count: 2 }
  });
});

app.post('/api/config/antiflood/:guildId', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('antiflood.json');
  const gid = req.params.guildId;
  const { enabled, nivel, accion, mute_time, log_channel } = req.body;
  if (!data[gid]) data[gid] = { enabled: false, nivel: 'medio', accion: 'mute', mute_time: 600, log_channel: null, settings: {} };
  if (enabled !== undefined) data[gid].enabled = enabled;
  if (accion) data[gid].accion = accion;
  if (mute_time !== undefined) data[gid].mute_time = parseInt(mute_time);
  if (log_channel !== undefined) data[gid].log_channel = log_channel ? parseInt(log_channel) : null;
  if (nivel) {
    data[gid].nivel = nivel;
    if (nivel === 'bajo')  data[gid].settings = { interval: 3, max_messages: 7, delete_count: 1 };
    if (nivel === 'medio') data[gid].settings = { interval: 4, max_messages: 5, delete_count: 2 };
    if (nivel === 'alto')  data[gid].settings = { interval: 5, max_messages: 3, delete_count: 3 };
  }
  saveJSON('antiflood.json', data);
  await notifyBot('antiflood', gid);
  res.json({ success: true });
});

// =============================================
// API — ANTIPING
// =============================================
app.get('/api/config/antiping/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('antiping.json');
  res.json(data[req.params.guildId] || {
    enabled: false, accion: 'mute', mute_time: 600,
    protected_users: [], protected_roles: [], whitelist_users: [], whitelist_roles: [], log_channel: null
  });
});

app.post('/api/config/antiping/:guildId', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('antiping.json');
  const gid = req.params.guildId;
  data[gid] = { ...(data[gid] || {}), ...req.body };
  saveJSON('antiping.json', data);
  await notifyBot('antiping', gid);
  res.json({ success: true });
});

// =============================================
// API — ANTIBOTS
// =============================================
app.get('/api/config/antibots/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('antibots.json');
  res.json(data[req.params.guildId] || { enabled: false, log_channel: null });
});

app.post('/api/config/antibots/:guildId', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('antibots.json');
  const gid = req.params.guildId;
  data[gid] = { ...(data[gid] || {}), ...req.body };
  saveJSON('antibots.json', data);
  await notifyBot('antibots', gid);
  res.json({ success: true });
});

// =============================================
// API — ANTIALTS
// =============================================
app.get('/api/config/antialts/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('antialts_config.json');
  res.json(data[req.params.guildId] || { dias: 7, logs: null });
});

app.post('/api/config/antialts/:guildId', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('antialts_config.json');
  const gid = req.params.guildId;
  const { dias, logs } = req.body;
  if (!data[gid]) data[gid] = { dias: 7, logs: null };
  if (dias !== undefined) data[gid].dias = parseInt(dias);
  if (logs !== undefined) data[gid].logs = logs ? parseInt(logs) : null;
  saveJSON('antialts_config.json', data);
  await notifyBot('antialts', gid);
  res.json({ success: true });
});

// =============================================
// API — LOGS
// =============================================
app.get('/api/config/logs/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('logs_config.json');
  res.json(data[req.params.guildId] || {
    enabled: false, channel: null,
    categories: { joins: true, roles: true, canales: true, mensajes: true, servidor: true }
  });
});

app.post('/api/config/logs/:guildId', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('logs_config.json');
  const gid = req.params.guildId;
  if (!data[gid]) data[gid] = { enabled: false, channel: null, categories: {} };
  const { enabled, channel, categories } = req.body;
  if (enabled !== undefined) data[gid].enabled = enabled;
  if (channel !== undefined) data[gid].channel = channel ? parseInt(channel) : null;
  if (categories) data[gid].categories = { ...data[gid].categories, ...categories };
  saveJSON('logs_config.json', data);
  await notifyBot('logs', gid);
  res.json({ success: true });
});

// =============================================
// API — WELCOME DM
// =============================================
app.get('/api/config/welcomedm/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('dm.json');
  const servers = data.servers || {};
  res.json(servers[req.params.guildId] || { enabled: false });
});

app.post('/api/config/welcomedm/:guildId', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('dm.json');
  if (!data.servers) data.servers = {};
  const gid = req.params.guildId;
  data.servers[gid] = { ...(data.servers[gid] || {}), ...req.body };
  saveJSON('dm.json', data);
  await notifyBot('welcomedm', gid);
  res.json({ success: true });
});

// =============================================
// API — BLACKLIST
// =============================================
app.get('/api/config/blacklist/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('blacklist_servers.json');
  res.json(data[req.params.guildId] || { users: {} });
});

app.post('/api/config/blacklist/:guildId/add', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('blacklist_servers.json');
  const gid = req.params.guildId;
  if (!data[gid]) data[gid] = { users: {} };
  const { userId, accion, minutos, razon } = req.body;
  if (!userId) return res.status(400).json({ error: 'userId requerido' });
  data[gid].users[userId] = { accion, minutos: parseInt(minutos) || 0, razon: razon || 'Sin razón' };
  saveJSON('blacklist_servers.json', data);
  await notifyBot('blacklist', gid);
  res.json({ success: true });
});

app.delete('/api/config/blacklist/:guildId/:userId', requireLogin, requireGuildAdmin, async (req, res) => {
  const data = loadJSON('blacklist_servers.json');
  const { guildId, userId } = req.params;
  if (data[guildId]?.users) delete data[guildId].users[userId];
  saveJSON('blacklist_servers.json', data);
  await notifyBot('blacklist', guildId);
  res.json({ success: true });
});

// =============================================
// API — VERIFICACION (solo lectura desde dashboard)
// =============================================
app.get('/api/config/verificacion/:guildId', requireLogin, requireGuildAdmin, (req, res) => {
  const data = loadJSON('verification.json');
  res.json(data[req.params.guildId] || {});
});

// =============================================
// INICIAR
// =============================================
app.listen(PORT, '0.0.0.0', () => {
  console.log(`\n✅ ModdyBot Dashboard v2 corriendo en http://localhost:${PORT}`);
  console.log(`👑 Owner ID: ${OWNER_ID}`);
  console.log(`🤖 Bot URL: ${BOT_URL || 'No configurada (sync desactivado)'}\n`);
});
