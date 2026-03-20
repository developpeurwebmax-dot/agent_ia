/**
 * business/auth.js — Authentification JWT + sidebar + utilitaires communs
 * Redirige vers business/connexion.html (pas freelance)
 */

const API = "https://agentia-production-aec3.up.railway.app";

// ── TOKEN ──
function getToken()        { return localStorage.getItem("jwt_token") || null; }
function setToken(t)       { localStorage.setItem("jwt_token", t); }
function removeToken()     { localStorage.removeItem("jwt_token"); localStorage.removeItem("user_cache"); }
function estConnecte()     { return !!getToken(); }

// ── HEADERS ──
function authHeaders() {
  return { "Content-Type": "application/json", "Authorization": "Bearer " + getToken() };
}

// ── CACHE USER ──
function getUserCache()    { try { return JSON.parse(localStorage.getItem("user_cache") || "null"); } catch(e) { return null; } }
function setUserCache(u)   { localStorage.setItem("user_cache", JSON.stringify(u)); }
function getUserId()       { var u = getUserCache(); return u ? u.id : "guest"; }

// ── DÉCONNEXION ──
// Redirige vers la page de connexion Business (pas Freelance)
function seDeconnecter() {
  removeToken();
  sessionStorage.setItem("session_expired", "1");
  window.location.href = "connexion.html";
}

// ── GESTION 401 GLOBALE ──
function gerer401() {
  removeToken();
  sessionStorage.setItem("session_expired", "1");
  window.location.href = "connexion.html";
}

// ── APPEL API AUTHENTIFIÉ ──
async function apiAuth(method, endpoint, body) {
  var opts = { method: method, headers: authHeaders() };
  if (body) opts.body = JSON.stringify(body);
  try {
    var res = await fetch(API + endpoint, opts);
    if (res.status === 401) { gerer401(); return null; }
    return res.json();
  } catch(e) {
    console.warn("API hors ligne :", endpoint);
    afficherBanniereHorsLigne();
    return null;
  }
}

// ── CHARGER PROFIL ──
async function chargerProfil() {
  var cached = getUserCache();
  if (cached) return cached;
  var json = await apiAuth("GET", "/auth/profil");
  if (json && json.statut === "ok") { setUserCache(json.data); return json.data; }
  return null;
}

// ── INIT SIDEBAR ──
// Vérifie l'auth, charge le profil, remplit la sidebar
async function initSidebar() {
  if (!estConnecte()) {
    window.location.href = "connexion.html";
    return null;
  }

  var user = await chargerProfil();
  if (!user) {
    window.location.href = "connexion.html";
    return null;
  }

  var el = function(id) { return document.getElementById(id); };
  if (el("sidebar-avatar")) el("sidebar-avatar").textContent = (user.prenom || "U")[0].toUpperCase();
  if (el("sidebar-nom"))    el("sidebar-nom").textContent    = (user.prenom || "") + " " + (user.nom || "");
  if (el("sidebar-role"))   el("sidebar-role").textContent   = user.metier || "Dirigeant";

  return user;
}

// ── BANNIÈRE API HORS LIGNE ──
function afficherBanniereHorsLigne() {
  if (document.getElementById("banniere-offline")) return;
  var b = document.createElement("div");
  b.id = "banniere-offline";
  b.style.cssText = "position:fixed;top:0;left:0;right:0;background:#1e1b4b;border-bottom:1px solid #ef4444;color:#f87171;font-size:0.82rem;font-weight:500;padding:8px 20px;text-align:center;z-index:9999;display:flex;align-items:center;justify-content:center;gap:8px";
  b.innerHTML = '⚠️ Serveur temporairement indisponible — certaines données peuvent ne pas s\'afficher. <button onclick="location.reload()" style="margin-left:12px;padding:2px 10px;border-radius:20px;border:1px solid #ef4444;background:transparent;color:#f87171;cursor:pointer;font-size:0.78rem">Réessayer</button>';
  document.body.prepend(b);
}

// ── SKELETON LOADER ──
function showSkeleton(ids) {
  ids.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = '<div style="height:18px;background:linear-gradient(90deg,var(--bg3) 25%,var(--border) 50%,var(--bg3) 75%);background-size:200% 100%;border-radius:6px;animation:shimmer 1.4s infinite;width:60%"></div>';
  });
}

(function() {
  if (!document.getElementById("shimmer-style")) {
    var s = document.createElement("style");
    s.id = "shimmer-style";
    s.textContent = "@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}";
    document.head.appendChild(s);
  }
})();