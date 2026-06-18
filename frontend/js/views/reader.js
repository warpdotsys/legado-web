/* Reader view: chapter list + reading content */
(function () {
  "use strict";
  const { el, icon, esc, loading, toast } = window.UI;
  const api = window.LegadoAPI;

  let state = {
    bookUrl: "", book: null, chapters: [], index: 0, content: "",
    loadingContent: false,
  };

  async function render(view, bookUrl) {
    state.bookUrl = bookUrl;
    view.appendChild(loading("打开书籍…"));

    // find the book object from the bookshelf (covers metadata)
    let book = null;
    try {
      const books = await api.getBookshelf();
      book = books.find((b) => b.bookUrl === bookUrl) || { bookUrl };
    } catch (e) { book = { bookUrl }; }
    state.book = book;
    state.index = book.durChapterIndex || 0;

    // load chapter list
    let chapters = [];
    try {
      chapters = await api.getChapterList(bookUrl);
      if (!Array.isArray(chapters)) chapters = [];
    } catch (e) {
      toast("加载目录失败: " + e.message, "err");
    }
    state.chapters = chapters;

    view.innerHTML = "";
    const wrap = el("div", { class: "reader" });

    // ---- left: chapter list ----
    const listPanel = el("div", { class: "reader-chapters" },
      el("div", { class: "chapters-head" },
        el("div", { class: "book-title", title: esc(book.name || "未命名") },
          esc(book.name || "未命名")),
        el("button", { class: "btn btn-ghost btn-sm", onclick: refreshToc },
          icon("refresh"), "更新目录")));
    const listEl = el("div", { class: "chapters-list" });
    if (chapters.length) {
      chapters.forEach((c, i) => {
        const item = el("div", {
          class: "chapter-item" + (i === state.index ? " current" : ""),
          onclick: () => goTo(i),
        },
          el("span", { class: "num" }, String(i + 1).padStart(3, "0")),
          el("span", {}, esc(c.title || ("第" + (i + 1) + "章"))));
        listEl.appendChild(item);
      });
    } else {
      listEl.appendChild(el("div", { class: "empty" },
        el("p", {}, "暂无目录，点击「更新目录」试试")));
    }
    listPanel.appendChild(listEl);
    wrap.appendChild(listPanel);

    // ---- right: content ----
    const main = el("div", { class: "reader-main" });
    const toolbar = el("div", { class: "reader-toolbar" },
      el("div", { class: "ch-title" },
        chapters[state.index] ? esc(chapters[state.index].title) : "—"));
    const actions = el("div", { class: "ch-actions" });
    const settingsBtn = el("button", { class: "btn btn-ghost btn-sm" },
      icon("settings"), "设置");
    actions.appendChild(settingsBtn);
    toolbar.appendChild(actions);
    main.appendChild(toolbar);

    const contentEl = el("div", { class: "reader-content" }, loading("加载正文…"));
    main.appendChild(contentEl);

    const navBar = el("div", { class: "reader-nav" },
      el("button", { class: "btn btn-ghost btn-sm", onclick: prev },
        icon("prev"), "上一章"),
      el("div", { class: "reader-progress" }, "— / —"),
      el("button", { class: "btn btn-ghost btn-sm", onclick: next },
        "下一章", icon("next")));
    main.appendChild(navBar);

    wrap.appendChild(main);
    view.appendChild(wrap);

    // settings popover
    const pop = buildSettings();
    main.style.position = "relative";
    main.appendChild(pop);
    settingsBtn.onclick = () => pop.classList.toggle("show");

    state.els = { contentEl, navBar, toolbar, listEl };
    if (chapters.length) {
      await loadContent();
    } else {
      contentEl.innerHTML = '<p class="load-error">没有可读章节</p>';
    }
  }

  function buildSettings() {
    const cfg = window.Store.config;
    const pop = el("div", { class: "settings-pop" });
    const add = (label, control) => {
      pop.appendChild(el("label", { class: "field-label" }, label));
      pop.appendChild(control);
    };
    const font = el("div", { class: "range-row" },
      el("input", { type: "range", min: "14", max: "28", value: String(cfg.fontSize) }),
      el("span", { class: "val" }, cfg.fontSize + "px"));
    font.querySelector("input").oninput = (e) => {
      cfg.fontSize = +e.target.value;
      font.querySelector(".val").textContent = cfg.fontSize + "px";
      applyTheme();
      window.Store.saveConfig();
    };
    add("字号", font);

    const lh = el("div", { class: "range-row" },
      el("input", { type: "range", min: "150", max: "250", value: String(cfg.lineHeight * 100) }),
      el("span", { class: "val" }, cfg.lineHeight));
    lh.querySelector("input").oninput = (e) => {
      cfg.lineHeight = +e.target.value / 100;
      lh.querySelector(".val").textContent = cfg.lineHeight.toFixed(2);
      applyTheme();
      window.Store.saveConfig();
    };
    add("行距", lh);

    const themeSel = el("select", { class: "select" },
      el("option", { value: "paper" }, "纸张"),
      el("option", { value: "sepia" }, "护眼"),
      el("option", { value: "dark" }, "夜间"));
    themeSel.value = cfg.theme;
    themeSel.onchange = (e) => {
      cfg.theme = e.target.value;
      applyTheme();
      window.Store.saveConfig();
    };
    add("主题", themeSel);
    return pop;
  }

  function applyTheme() {
    const cfg = window.Store.config;
    const v = window.Store.themeVars(cfg.theme);
    const c = state.els && state.els.contentEl;
    if (c) {
      c.style.background = v.bg;
      c.style.color = v.text;
      c.style.fontSize = cfg.fontSize + "px";
      c.style.lineHeight = cfg.lineHeight;
    }
  }

  async function loadContent() {
    if (!state.chapters.length) return;
    const { contentEl, navBar } = state.els;
    contentEl.innerHTML = "";
    contentEl.appendChild(loading("加载正文…"));
    state.loadingContent = true;
    try {
      const text = await api.getBookContent(state.bookUrl, state.index);
      state.content = text || "";
      contentEl.innerHTML = "";
      const ch = state.chapters[state.index];
      contentEl.appendChild(el("h2", { class: "ch-heading" }, esc(ch.title || "")));
      const paras = String(text).split(/\n+/).filter((s) => s.trim());
      paras.forEach((p) => {
        if (/^https?:\/\/.+\.(png|jpe?g|gif|webp)/i.test(p.trim())) {
          contentEl.appendChild(el("img", { class: "content-img", src: p.trim() }));
        } else {
          contentEl.appendChild(el("p", {}, esc(p)));
        }
      });
      if (!paras.length)
        contentEl.appendChild(el("p", { class: "text-muted" }, "（本章无内容）"));
    } catch (e) {
      contentEl.innerHTML = "";
      contentEl.appendChild(el("p", { class: "load-error" }, "加载失败: " + esc(e.message)));
    } finally {
      state.loadingContent = false;
      updateNav();
      contentEl.scrollTop = 0;
      // persist progress
      saveProgress();
    }
  }

  function updateNav() {
    const { navBar, toolbar, listEl } = state.els;
    navBar.querySelector(".reader-progress").textContent =
      (state.index + 1) + " / " + state.chapters.length;
    toolbar.querySelector(".ch-title").textContent =
      state.chapters[state.index] ? state.chapters[state.index].title : "—";
    listEl.querySelectorAll(".chapter-item").forEach((it, i) => {
      it.classList.toggle("current", i === state.index);
    });
    const current = listEl.children[state.index];
    if (current) current.scrollIntoView({ block: "nearest" });
  }

  function goTo(i) {
    if (i < 0 || i >= state.chapters.length || state.loadingContent) return;
    state.index = i;
    loadContent();
  }
  function prev() { goTo(state.index - 1); }
  function next() { goTo(state.index + 1); }

  async function refreshToc() {
    toast("正在更新目录…");
    try {
      const chapters = await api.refreshToc(state.bookUrl);
      if (Array.isArray(chapters)) {
        state.chapters = chapters;
        state.els.listEl.innerHTML = "";
        chapters.forEach((c, i) => {
          state.els.listEl.appendChild(el("div", {
            class: "chapter-item" + (i === state.index ? " current" : ""),
            onclick: () => goTo(i),
          },
            el("span", { class: "num" }, String(i + 1).padStart(3, "0")),
            el("span", {}, esc(c.title || ("第" + (i + 1) + "章")))));
        });
        toast("目录已更新 (" + chapters.length + " 章)", "ok");
        updateNav();
      }
    } catch (e) { toast("更新失败: " + e.message, "err"); }
  }

  async function saveProgress() {
    if (!state.book) return;
    try {
      await api.saveBookProgress({
        name: state.book.name,
        author: state.book.author,
        durChapterIndex: state.index,
        durChapterPos: 0,
        durChapterTime: Date.now(),
        durChapterTitle: state.chapters[state.index]
          ? state.chapters[state.index].title : null,
      });
    } catch (e) { /* silent */ }
  }

  // keyboard nav
  document.addEventListener("keydown", (e) => {
    if (!location.hash.startsWith("#/read/")) return;
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (e.key === "ArrowLeft") prev();
    else if (e.key === "ArrowRight") next();
  });

  window.ReaderView = { render, applyTheme };
})();
