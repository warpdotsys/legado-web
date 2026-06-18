/* Search view — searches all enabled book sources via /searchBook websocket */
(function () {
  "use strict";
  const { el, icon, esc, loading, emptyState, toast } = window.UI;
  const api = window.LegadoAPI;

  let st = { key: "", results: [], sources: [], searching: false, sock: null,
    added: new Set() };

  async function render(view) {
    view.innerHTML = "";

    view.appendChild(el("div", { class: "page-head" },
      el("div", { class: "page-title" }, icon("search"), "搜索")));

    const bar = el("div", { class: "search-bar" },
      el("span", { class: "icon" }, icon("search")));
    const input = el("input", { type: "text", placeholder: "输入书名或作者，搜索全部启用的书源…" });
    bar.appendChild(input);
    const btn = el("button", { class: "btn btn-primary" }, "搜索");
    bar.appendChild(btn);

    const sourceInfo = el("div", { class: "search-progress" });
    const resultsWrap = el("div", { class: "search-results" });

    view.appendChild(bar);
    view.appendChild(sourceInfo);
    view.appendChild(resultsWrap);

    async function ensureSources() {
      if (!st.sources.length) {
        try { st.sources = await api.getBookSources(); }
        catch (e) { st.sources = []; }
      }
      const enabled = st.sources.filter((s) => s.enabled && s.searchUrl);
      sourceInfo.innerHTML = "";
      sourceInfo.appendChild(el("span", {}, "可用书源："));
      sourceInfo.appendChild(el("span", { class: "count" }, enabled.length + " 个"));
      return enabled;
    }
    await ensureSources();

    function doSearch() {
      const key = input.value.trim();
      if (!key) { toast("请输入关键词", "err"); return; }
      if (st.searching && st.sock) { try { st.sock.close(); } catch (e) {} }
      st.key = key;
      st.results = [];
      st.added = new Set();
      st.searching = true;
      btn.disabled = true;
      btn.textContent = "搜索中…";
      resultsWrap.innerHTML = "";
      sourceInfo.appendChild(el("span", {}, "  · 搜索中…"));

      st.sock = api.search(key, {
        onMessage: (data) => {
          if (Array.isArray(data)) {
            data.forEach((r) => st.results.push(r));
            renderResults();
          } else if (data && data.finished) {
            finish();
          } else if (data && data.isSuccess === false) {
            toast(data.errorMsg, "err");
          }
        },
        onClose: () => finish(),
        onError: () => { toast("搜索连接错误", "err"); finish(); },
      });
    }

    function finish() {
      st.searching = false;
      btn.disabled = false;
      btn.textContent = "搜索";
      sourceInfo.lastChild && sourceInfo.lastChild.remove();
      if (!st.results.length) {
        resultsWrap.innerHTML = "";
        resultsWrap.appendChild(emptyState("未找到结果", "没有书源返回结果，请先在「书源」页添加并启用带搜索URL的书源。", "search"));
      }
    }

    function renderResults() {
      resultsWrap.innerHTML = "";
      st.results.forEach((r) => resultsWrap.appendChild(resultCard(r)));
    }

    function resultCard(r) {
      const added = st.added.has(r.bookUrl);
      const card = el("div", { class: "result-card" + (added ? " added" : "") });
      const cover = el("div", { class: "result-cover" });
      if (r.coverUrl) {
        const img = el("img", { alt: r.name, src: api.coverUrl(r.coverUrl),
          style: "width:100%;height:100%;object-fit:cover;" });
        img.addEventListener("error", () => {
          img.remove(); cover.appendChild(el("div", {}, esc(r.name)));
        });
        cover.appendChild(img);
      } else {
        cover.appendChild(el("div", {}, esc(r.name)));
      }
      card.appendChild(cover);
      card.appendChild(el("div", { class: "result-info" },
        el("div", { class: "result-name" }, esc(r.name)),
        el("div", { class: "result-author" }, esc(r.author || "")),
        r.kind ? el("div", { class: "result-kind" }, esc(r.kind)) : null,
        r.intro ? el("div", { class: "result-intro" }, esc(r.intro)) : null,
        el("div", { class: "result-source" }, added ? "✓ 已加入书架" : esc(r.originName || r.origin || ""))));
      card.addEventListener("click", async () => {
        if (st.added.has(r.bookUrl)) {
          location.hash = "#/read/" + encodeURIComponent(r.bookUrl);
          return;
        }
        try {
          await api.saveBook({
            bookUrl: r.bookUrl, name: r.name, author: r.author,
            coverUrl: r.coverUrl, intro: r.intro, kind: r.kind,
            origin: r.origin, originName: r.originName, type: r.type,
            tocUrl: "", totalChapterNum: 0,
          });
          st.added.add(r.bookUrl);
          card.classList.add("added");
          card.querySelector(".result-source").textContent = "✓ 已加入书架";
          toast("已加入书架: " + r.name, "ok");
        } catch (e) { toast("加入失败: " + e.message, "err"); }
      });
      return card;
    }

    input.addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
    btn.addEventListener("click", doSearch);

    // show empty state initially
    resultsWrap.appendChild(emptyState("开始搜索", "输入书名后回车，将从全部启用书源检索。", "search"));
    setTimeout(() => input.focus(), 50);
  }

  window.SearchView = { render };
})();
