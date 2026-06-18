/* App bootstrap */
(function () {
  "use strict";

  async function checkBackend() {
    const dot = document.getElementById("connStatus");
    try {
      await window.LegadoAPI.getBookSources();
      dot.className = "conn-status ok";
      dot.title = "已连接后端 (端口 1122)";
    } catch (e) {
      dot.className = "conn-status err";
      dot.title = "后端未连接: " + (e.message || e);
    }
  }

  async function boot() {
    await window.Store.loadConfig();
    await checkBackend();
    window.addEventListener("hashchange", window.Router.dispatch);
    if (!location.hash) location.hash = "#/bookshelf";
    else window.Router.dispatch();
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
