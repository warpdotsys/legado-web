/* UI helpers: toast, modal, escape, icon set, DOM builder. */
(function () {
  "use strict";

  const ICONS = {
    book: "📖", search: "🔍", source: "📡", rss: "📰", replace: "🔁",
    add: "＋", edit: "✎", delete: "🗑", refresh: "↻", back: "←",
    prev: "‹", next: "›", settings: "⚙", close: "×", check: "✓",
    debug: "🐞", import: "📥", export: "📤", grid: "▦", list: "≡",
    about: "ℹ", star: "★", clock: "◷",
  };

  function icon(name) { return ICONS[name] || ""; }

  function esc(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        if (k === "class") node.className = attrs[k];
        else if (k === "html") node.innerHTML = attrs[k];
        else if (k.startsWith("on") && typeof attrs[k] === "function")
          node.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        else if (attrs[k] != null) node.setAttribute(k, attrs[k]);
      }
    }
    for (const c of children) {
      if (c == null || c === false) continue;
      if (Array.isArray(c)) c.forEach((x) => x && node.append(_toNode(x)));
      else node.append(_toNode(c));
    }
    return node;
  }

  function _toNode(x) {
    if (x instanceof Node) return x;
    return document.createTextNode(String(x));
  }

  function toast(msg, type = "info", ms = 2600) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast show " + type;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (t.className = "toast"), ms);
  }

  function modal({ title, body, wide, onClose, footer }) {
    const root = document.getElementById("modalRoot");
    root.innerHTML = "";
    const backdrop = el("div", { class: "modal-backdrop" });
    const box = el("div", { class: "modal" + (wide ? " wide" : "") });
    box.appendChild(el("div", { class: "modal-head" },
      el("div", { class: "modal-title" }, title),
      el("button", { class: "modal-close", onclick: close }, icon("close")),
    ));
    const bodyEl = el("div", { class: "modal-body" });
    if (typeof body === "string") bodyEl.innerHTML = body;
    else if (body instanceof Node) bodyEl.appendChild(body);
    else if (Array.isArray(body)) body.forEach((n) => bodyEl.append(n));
    box.appendChild(bodyEl);
    if (footer) {
      const foot = el("div", { class: "modal-foot" });
      (Array.isArray(footer) ? footer : [footer]).forEach((n) => foot.append(n));
      box.appendChild(foot);
    }
    root.appendChild(backdrop);
    root.appendChild(box);
    root.classList.add("show");

    function close() {
      root.classList.remove("show");
      root.innerHTML = "";
      if (onClose) onClose();
    }
    backdrop.addEventListener("click", close);
    return { close, body: bodyEl, box };
  }

  // simpler confirm using modal()
  function confirmBox(msg, onYes, { title = "确认", danger = false } = {}) {
    let m;
    const close = () => m.close();
    m = modal({
      title,
      body: el("p", { style: "color:var(--text-soft);font-size:14px;" }, msg),
      footer: [
        el("button", { class: "btn btn-ghost", onclick: close }, "取消"),
        el("button", {
          class: "btn " + (danger ? "btn-danger" : "btn-primary"),
          onclick: () => { close(); onYes && onYes(); },
        }, "确定"),
      ],
    });
  }

  function loading(msg = "加载中…") {
    return el("div", { class: "loading-page" },
      el("div", { class: "spinner" }),
      el("div", {}, msg));
  }

  function emptyState(title, msg, icon = "book") {
    return el("div", { class: "empty" },
      el("div", { class: "empty-icon" }, ICONS[icon]),
      el("h3", {}, title),
      el("p", {}, msg));
  }

  window.UI = { icon, icons: ICONS, esc, el, toast, modal, confirmBox,
    loading, emptyState };
})();
