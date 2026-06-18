/* legado Web API client.
 *
 * Talks to the legado-compatible web service on the same origin (port 1122),
 * matching the exact endpoints defined in
 * app/src/main/java/io/legado/app/web/HttpServer.kt and the WebSocketServer
 * routes (/searchBook, /bookSourceDebug, /rssSourceDebug).
 *
 * Responses follow legado's ReturnData shape: { isSuccess, errorMsg, data }.
 */
(function () {
  "use strict";

  const BASE = location.origin.replace(/^http/, "http"); // same-origin http
  const WS_BASE = (location.protocol === "https:" ? "wss:" : "ws:") +
    "//" + location.host;

  function parseData(resp) {
    if (!resp.isSuccess) {
      const err = new Error(resp.errorMsg || "请求失败");
      err.legado = resp;
      throw err;
    }
    return resp.data;
  }

  async function get(path, params) {
    let url = path;
    if (params) {
      const qs = new URLSearchParams();
      for (const k in params) {
        if (params[k] != null && params[k] !== "")
          qs.set(k, params[k]);
      }
      const s = qs.toString();
      if (s) url += "?" + s;
    }
    const r = await fetch(url, { method: "GET", credentials: "same-origin" });
    return parseData(await r.json());
  }

  async function post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: typeof body === "string" ? body : JSON.stringify(body),
    });
    return parseData(await r.json());
  }

  function coverUrl(path) {
    if (!path) return "";
    if (/^https?:\/\//.test(path) || path.startsWith(location.origin)) return path;
    if (path.startsWith("/")) return location.origin + path;
    return location.origin + "/cover?path=" + encodeURIComponent(path);
  }

  // ---- WebSocket helper (search / debug) ----
  function ws(route, payload, { onMessage, onClose, onError } = {}) {
    const url = WS_BASE + route;
    const sock = new WebSocket(url);
    sock.onopen = () => {
      try { sock.send(JSON.stringify(payload)); } catch (e) { onError && onError(e); }
    };
    sock.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        onMessage && onMessage(data, ev);
      } catch {
        onMessage && onMessage(ev.data, ev);
      }
    };
    sock.onclose = (ev) => onClose && onClose(ev);
    sock.onerror = (ev) => onError && onError(ev);
    return sock;
  }

  window.LegadoAPI = {
    // Books
    getBookshelf: () => get("/getBookshelf"),
    getChapterList: (bookUrl) => get("/getChapterList", { url: bookUrl }),
    refreshToc: (bookUrl) => get("/refreshToc", { url: bookUrl }),
    getBookContent: (bookUrl, index) =>
      get("/getBookContent", { url: bookUrl, index }),
    saveBook: (book) => post("/saveBook", book),
    deleteBook: (book) => post("/deleteBook", book),
    saveBookProgress: (p) => post("/saveBookProgress", p),
    getReadConfig: () => get("/getReadConfig"),
    saveReadConfig: (cfg) => post("/saveReadConfig", cfg),

    // Book sources
    getBookSources: () => get("/getBookSources"),
    getBookSource: (url) => get("/getBookSource", { url }),
    saveBookSource: (s) => post("/saveBookSource", s),
    saveBookSources: (arr) => post("/saveBookSources", arr),
    deleteBookSources: (arr) => post("/deleteBookSources", arr),

    // RSS sources
    getRssSources: () => get("/getRssSources"),
    getRssSource: (url) => get("/getRssSource", { url }),
    saveRssSource: (s) => post("/saveRssSource", s),
    saveRssSources: (arr) => post("/saveRssSources", arr),
    deleteRssSources: (arr) => post("/deleteRssSources", arr),

    // Replace rules
    getReplaceRules: () => get("/getReplaceRules"),
    saveReplaceRule: (r) => post("/saveReplaceRule", r),
    deleteReplaceRule: (r) => post("/deleteReplaceRule", r),
    testReplaceRule: (rule, text) => post("/testReplaceRule", { rule, text }),

    // Search + debug (websocket)
    search: (key, handlers) => ws("/searchBook", { key }, handlers),
    debugSource: (tag, key, handlers) =>
      ws("/bookSourceDebug", { tag, key }, handlers),
    debugRss: (tag, key, handlers) =>
      ws("/rssSourceDebug", { tag, key }, handlers),

    coverUrl,
  };
})();
