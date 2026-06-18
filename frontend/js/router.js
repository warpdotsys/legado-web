/* Hash router */
(function () {
  "use strict";

  const routes = [
    { path: /^\/?$/, view: "BookshelfView", nav: "bookshelf" },
    { path: /^\/bookshelf\/?$/, view: "BookshelfView", nav: "bookshelf" },
    { path: /^\/read\/(.+)$/, view: "ReaderView", nav: "bookshelf", param: true },
    { path: /^\/search\/?$/, view: "SearchView", nav: "search" },
    { path: /^\/bookSource\/?$/, view: "BookSourceView", nav: "bookSource" },
    { path: /^\/rssSource\/?$/, view: "RssSourceView", nav: "rssSource" },
    { path: /^\/replaceRule\/?$/, view: "ReplaceRuleView", nav: "replaceRule" },
    { path: /^\/about\/?$/, view: "AboutView", nav: "about" },
  ];

  function current() {
    let hash = location.hash.replace(/^#/, "");
    if (!hash) hash = "/";
    if (!hash.startsWith("/")) hash = "/" + hash;
    for (const r of routes) {
      const m = hash.match(r.path);
      if (m) return { ...r, arg: r.param ? decodeURIComponent(m[1]) : null };
    }
    return null;
  }

  function markNav(navName) {
    document.querySelectorAll(".nav-item").forEach((a) => {
      a.classList.toggle("active", a.dataset.route === navName);
    });
  }

  async function dispatch() {
    const route = current();
    const view = document.getElementById("view");
    view.innerHTML = "";
    if (!route) {
      view.appendChild(window.UI.el("div", { class: "empty" },
        window.UI.el("div", { class: "empty-icon" }, "?"),
        window.UI.el("h3", {}, "页面不存在"),
        window.UI.el("p", {}, "返回书架继续阅读。")));
      markNav("");
      return;
    }
    markNav(route.nav);
    view.classList.remove("view-enter");
    void view.offsetWidth;
    view.classList.add("view-enter");
    const V = window[route.view];
    try {
      if (route.arg !== null) await V.render(view, route.arg);
      else await V.render(view);
      // apply reader theme if applicable
      if (route.view === "ReaderView" && window.ReaderView.applyTheme)
        window.ReaderView.applyTheme();
    } catch (e) {
      view.innerHTML = "";
      view.appendChild(window.UI.el("div", { class: "empty" },
        window.UI.el("div", { class: "empty-icon" }, "!"),
        window.UI.el("h3", {}, "加载出错"),
        window.UI.el("p", {}, window.UI.esc(e.message || String(e)))));
    }
    view.scrollIntoView({ block: "start" });
  }

  window.Router = { dispatch };
})();
