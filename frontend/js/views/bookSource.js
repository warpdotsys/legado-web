/* Book sources management: list / add / edit / delete / debug / import-export */
(function () {
  "use strict";
  const { el, icon, esc, toast, modal, confirmBox, loading, emptyState } = window.UI;
  const api = window.LegadoAPI;

  let st = { sources: [], filter: "" };

  async function render(view) {
    view.innerHTML = "";
    view.appendChild(el("div", { class: "page-head" },
      el("div", { class: "page-title" }, icon("source"), "书源管理")));

    view.appendChild(toolbar());
    const wrap = el("div");
    view.appendChild(wrap);
    await reload(wrap);
  }

  function toolbar() {
    const bar = el("div", { class: "source-toolbar" });
    const search = el("input", { class: "input", style: "max-width:260px;",
      placeholder: "按名称/URL/分组筛选…" });
    search.oninput = () => { st.filter = search.value.trim().toLowerCase(); repaint(); };
    bar.appendChild(search);
    bar.appendChild(el("div", { class: "grow" }));
    bar.appendChild(el("button", { class: "btn btn-ghost", onclick: importBox },
      icon("import"), "导入"));
    bar.appendChild(el("button", { class: "btn btn-ghost", onclick: exportAll },
      icon("export"), "导出"));
    bar.appendChild(el("button", { class: "btn btn-primary", onclick: () => editSource(null) },
      icon("add"), "新建书源"));
    return bar;
  }

  async function reload(wrap) {
    wrap.innerHTML = "";
    wrap.appendChild(loading("加载书源…"));
    try {
      st.sources = await api.getBookSources();
    } catch (e) {
      st.sources = [];
      toast(e.message, "err");
    }
    wrap.innerHTML = "";
    if (!st.sources.length) {
      wrap.appendChild(emptyState("暂无书源", "新建书源或导入书源 JSON 即可开始搜索阅读。", "source"));
      return;
    }
    wrap.appendChild(table());
  }

  function table() {
    const list = filtered();
    const t = el("table", { class: "source-table" });
    t.appendChild(el("thead", {}, el("tr", {},
      el("th", {}, "名称"), el("th", {}, "URL"), el("th", {}, "分组"),
      el("th", {}, "状态"), el("th", {}, "响应"), el("th", { style: "text-align:right" }, "操作"))));
    const tb = el("tbody", {});
    list.forEach((s) => {
      tb.appendChild(el("tr", {},
        el("td", { class: "src-name" }, esc(s.bookSourceName)),
        el("td", { class: "src-url", title: esc(s.bookSourceUrl) }, esc(s.bookSourceUrl)),
        el("td", { class: "src-group" }, esc(s.bookSourceGroup || "—")),
        el("td", {}, el("span", { class: "badge " + (s.enabled ? "on" : "off") },
          s.enabled ? "启用" : "禁用")),
        el("td", { class: "text-mono" }, (s.respondTime / 1000).toFixed(1) + "s"),
        el("td", { class: "row-actions" },
          el("button", { class: "btn btn-sm btn-ghost", title: "调试",
            onclick: () => debugSource(s) }, icon("debug")),
          el("button", { class: "btn btn-sm btn-ghost", title: "编辑",
            onclick: () => editSource(s) }, icon("edit")),
          el("button", { class: "btn btn-sm btn-danger", title: "删除",
            onclick: () => del(s) }, icon("delete")))));
    });
    t.appendChild(tb);
    return el("div", { class: "source-table-wrap" }, t);
  }

  function filtered() {
    if (!st.filter) return st.sources;
    return st.sources.filter((s) =>
      (s.bookSourceName + s.bookSourceUrl + (s.bookSourceGroup || ""))
        .toLowerCase().includes(st.filter));
  }

  function repaint() {
    const view = document.getElementById("view");
    const wrap = view.querySelector(".source-table-wrap");
    if (wrap) wrap.replaceWith(table());
  }

  // ---- edit / create ----
  function editSource(src) {
    const isNew = !src;
    const data = src ? JSON.parse(JSON.stringify(src)) : blankSource();
    const form = buildForm(data);
    let mod;
    mod = modal({
      title: (isNew ? "新建书源" : "编辑书源"), wide: true,
      body: form,
      footer: [
        el("button", { class: "btn btn-ghost", onclick: () => mod.close() }, "取消"),
        el("button", { class: "btn btn-primary", onclick: save }, "保存"),
      ],
    });
    function save() {
      const errs = validate(data);
      if (errs.length) { toast(errs.join("；"), "err"); return; }
      api.saveBookSource(data).then(() => {
        mod.close();
        toast(isNew ? "已添加书源" : "已更新书源", "ok");
        render(document.getElementById("view"));
      }).catch((e) => toast(e.message, "err"));
    }
  }

  function blankSource() {
    return {
      bookSourceUrl: "", bookSourceName: "", bookSourceGroup: "",
      bookSourceType: 0, enabled: true, enabledExplore: true,
      searchUrl: "", exploreUrl: "", header: "",
      ruleSearch: { bookList: "", name: "", author: "", intro: "", kind: "",
        lastChapter: "", bookUrl: "", coverUrl: "" },
      ruleBookInfo: { name: "", author: "", intro: "", kind: "", coverUrl: "",
        lastChapter: "", tocUrl: "", wordCount: "" },
      ruleToc: { chapterList: "", chapterName: "", chapterUrl: "", nextTocUrl: "" },
      ruleContent: { content: "", replaceRegex: "" },
    };
  }

  function buildForm(d) {
    const f = el("div", { class: "source-form" });
    const inp = (label, key, full, ph) => {
      const i = el("input", { class: "input", value: esc(d[key] || ""), placeholder: ph || "" });
      i.oninput = () => d[key] = i.value;
      return el("div", { class: "field" + (full ? " full" : "") },
        el("label", { class: "field-label" }, label), i);
    };
    const ta = (label, key, full, ph) => {
      const i = el("textarea", { class: "textarea", placeholder: ph || "", rows: "2" });
      i.value = d[key] || "";
      i.oninput = () => d[key] = i.value;
      return el("div", { class: "field" + (full ? " full" : "") },
        el("label", { class: "field-label" }, label), i);
    };
    f.appendChild(inp("源名称 *", "bookSourceName", false));
    f.appendChild(inp("源URL *", "bookSourceUrl", false));
    f.appendChild(inp("分组", "bookSourceGroup", false));
    const typeSel = el("select", { class: "select" },
      el("option", { value: "0" }, "文本"),
      el("option", { value: "1" }, "音频"),
      el("option", { value: "2" }, "图片"));
    typeSel.value = String(d.bookSourceType || 0);
    typeSel.onchange = () => d.bookSourceType = +typeSel.value;
    f.appendChild(el("div", { class: "field" },
      el("label", { class: "field-label" }, "类型"), typeSel));

    f.appendChild(ta("搜索URL", "searchUrl", true, "https://x.com/search?q={{key}}"));
    f.appendChild(ta("发现URL", "exploreUrl", true));
    f.appendChild(ta("请求头(JSON)", "header", true, '{"User-Agent":"..."}'));

    // rule sections
    f.appendChild(ruleSection("搜索规则", d.ruleSearch || {}, [
      ["bookList", "列表规则"], ["name", "书名"], ["author", "作者"],
      ["intro", "简介"], ["kind", "分类"], ["lastChapter", "最新章节"],
      ["bookUrl", "详情URL"], ["coverUrl", "封面URL"]]));
    f.appendChild(ruleSection("详情规则", d.ruleBookInfo || {}, [
      ["name", "书名"], ["author", "作者"], ["intro", "简介"],
      ["kind", "分类"], ["coverUrl", "封面URL"], ["lastChapter", "最新章节"],
      ["tocUrl", "目录URL"], ["wordCount", "字数"]]));
    f.appendChild(ruleSection("目录规则", d.ruleToc || {}, [
      ["chapterList", "章节列表"], ["chapterName", "章节名"],
      ["chapterUrl", "章节URL"], ["nextTocUrl", "下一页URL"]]));
    f.appendChild(ruleSection("正文规则", d.ruleContent || {}, [
      ["content", "正文规则"], ["replaceRegex", "替换净化(正则##替换)"]]));

    const enRow = el("div", { class: "field full" },
      el("label", { class: "field-label" }, "选项"));
    const en = el("input", { type: "checkbox" }); en.checked = !!d.enabled;
    en.onchange = () => d.enabled = en.checked;
    enRow.appendChild(el("label", { style: "display:flex;align-items:center;gap:6px;font-size:13px;" },
      en, " 启用此书源"));
    f.appendChild(enRow);
    return f;
  }

  function ruleSection(title, obj, fields) {
    const sec = el("div", { class: "rule-section" });
    sec.appendChild(el("div", { class: "rule-section-title" }, icon("source"), title));
    fields.forEach(([k, label]) => {
      const i = el("input", { class: "input", value: esc(obj[k] || ""), placeholder: "" });
      i.oninput = () => obj[k] = i.value;
      sec.appendChild(el("div", { class: "field", style: "margin-bottom:8px" },
        el("label", { class: "field-label" }, label), i));
    });
    return sec;
  }

  function validate(d) {
    const e = [];
    if (!d.bookSourceName) e.push("源名称不能为空");
    if (!d.bookSourceUrl) e.push("源URL不能为空");
    return e;
  }

  function del(s) {
    confirmBox(`删除书源「${s.bookSourceName}」？`, async () => {
      try { await api.deleteBookSources([s]); toast("已删除", "ok");
        render(document.getElementById("view")); }
      catch (e) { toast(e.message, "err"); }
    }, { danger: true, title: "删除书源" });
  }

  // ---- debug ----
  function debugSource(s) {
    const console_ = el("div", { class: "debug-console" },
      "等待调试…\n输入搜索关键词后开始。\n");
    const keyInput = el("input", { class: "input", placeholder: "搜索关键词 (如: 斗破苍穹)" });
    const runBtn = el("button", { class: "btn btn-primary" }, icon("debug"), "开始调试");
    modal({
      title: "调试书源 — " + s.bookSourceName, wide: true,
      body: [
        el("div", { class: "row mb-16" }, keyInput, runBtn),
        console_,
      ],
    });
    runBtn.onclick = () => {
      const key = keyInput.value.trim();
      if (!key) { toast("请输入关键词", "err"); return; }
      console_.innerHTML = "";
      log("开始调试书源 " + s.bookSourceName + "，关键词：" + key, "info");
      runBtn.disabled = true;
      api.debugSource(s.bookSourceUrl, key, {
        onMessage: (data) => {
          if (typeof data === "string") log(data);
          else if (data.type === "debug") log(data.msg, "info");
          else if (data.type === "result")
            log("  ✓ " + (data.name || "") + " — " + (data.author || "") + "  " + (data.url || ""), "ok");
          else if (data.isSuccess === false) log(data.errorMsg, "err");
          console_.scrollTop = console_.scrollHeight;
        },
        onClose: () => { runBtn.disabled = false; log("—— 调试结束 ——", "info"); },
        onError: () => { runBtn.disabled = false; log("连接错误", "err"); },
      });
    };
    function log(msg, cls = "") {
      const line = el("div", { class: "line" + (cls ? " line-" + cls : "") }, msg + "\n");
      console_.appendChild(line);
      console_.scrollTop = console_.scrollHeight;
    }
  }

  // ---- import / export ----
  function importBox() {
    const ta = el("textarea", { class: "textarea", rows: "12",
      placeholder: "粘贴书源 JSON（单个对象或数组）…" });
    let mod;
    mod = modal({
      title: "导入书源", body: ta,
      footer: [
        el("button", { class: "btn btn-ghost", onclick: () => mod.close() }, "取消"),
        el("button", { class: "btn btn-primary", onclick: doImport }, "导入"),
      ],
    });
    async function doImport() {
      let arr;
      try {
        const v = JSON.parse(ta.value.trim());
        arr = Array.isArray(v) ? v : [v];
      } catch (e) { toast("JSON 格式错误", "err"); return; }
      try {
        const res = await api.saveBookSources(arr);
        toast("成功导入 " + (Array.isArray(res) ? res.length : arr.length) + " 个书源", "ok");
        mod.close();
        render(document.getElementById("view"));
      } catch (e) { toast(e.message, "err"); }
    }
  }

  function exportAll() {
    if (!st.sources.length) { toast("没有可导出的书源", "err"); return; }
    const blob = new Blob([JSON.stringify(st.sources, null, 2)],
      { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob),
      download: "legado_book_sources.json" });
    document.body.appendChild(a); a.click(); a.remove();
    toast("已导出 " + st.sources.length + " 个书源", "ok");
  }

  window.BookSourceView = { render };
})();
