/**
 * role-guard.js — Garde d'accès par rôle pour le module Business
 *
 * À inclure AVANT auth.js dans chaque page protégée.
 * Expose :
 *   - window.ROLE_UTILISATEUR  (string : "admin", "rh", "comptable", "commercial", "employe")
 *   - window.ENTREPRISE_ID_GLOBAL (string : premier entreprise_id de l'utilisateur)
 *   - verifierAccesPage(pagesAutorisees)  → async, redirige si employé non autorisé
 */

(function () {
  // ── Réutilise les helpers de auth.js s'ils sont déjà chargés, sinon mini-impl ──
  function _getToken() {
    return localStorage.getItem("jwt_token") || null;
  }
  function _estConnecte() {
    return !!_getToken();
  }
  function _authHeaders() {
    return {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + _getToken()
    };
  }

  // Nom du fichier courant (ex: "dashboard.html")
  function _nomPageCourante() {
    var parts = window.location.pathname.split("/");
    return parts[parts.length - 1] || "index.html";
  }

  /**
   * Vérifie le rôle de l'utilisateur et redirige si nécessaire.
   * @param {string[]} pagesAutorisees - Liste des noms de fichiers HTML accessibles.
   *   Passer [] pour bloquer l'employé sur toutes les pages (sauf espace-employe.html).
   *   Passer ["espace-employe.html"] pour la page employé elle-même.
   */
  window.verifierAccesPage = async function (pagesAutorisees) {
    // Si déjà résolu dans cette session (navigation sans rechargement)
    if (window.ROLE_UTILISATEUR) {
      _appliquerGarde(window.ROLE_UTILISATEUR, pagesAutorisees);
      return;
    }

    if (!_estConnecte()) {
      window.location.href = "connexion.html";
      return;
    }

    try {
      var API = (typeof window !== "undefined" && window.API) || "https://agent-ia-zgha.onrender.com";
      var res  = await fetch(API + "/business/entreprises", { headers: _authHeaders() });
      if (res.status === 401) {
        localStorage.removeItem("jwt_token");
        window.location.href = "connexion.html";
        return;
      }
      var json = await res.json();
      var entreprises = (json && json.data && json.data.entreprises) || [];
      if (!entreprises.length) return;

      var ent  = entreprises[0];
      var role = ent.role || "employe";

      // Stocker globalement pour réutilisation par auth.js et les pages
      window.ROLE_UTILISATEUR    = role;
      window.ENTREPRISE_ID_GLOBAL = ent.id;

      _appliquerGarde(role, pagesAutorisees);
    } catch (e) {
      // En cas d'erreur réseau on laisse passer (auth.js gèrera)
    }
  };

  function _appliquerGarde(role, pagesAutorisees) {
    if (role !== "employe") return;

    // L'employé est toujours autorisé sur espace-employe.html
    var autorisees = (pagesAutorisees || []).concat(["espace-employe.html"]);
    var pageCourante = _nomPageCourante();

    if (autorisees.indexOf(pageCourante) === -1) {
      window.location.replace("espace-employe.html");
    }
  }
})();
