/* RSS sources management */
(function () {
  "use strict";
  const { el, icon, esc, toast, modal, confirmBox, loading, emptyState } = window.UI;
  const api = window.LegadoAPI;

  let st = { sources: [], filter: "" };

  async function render(view) {
    view.innerHTML = "";
    view.appendChild(el("div", { class: "page-head" },
      el("div", { class: "page-title" }, icon("rss"), "订阅源管理")));

    const bar = el("div", { class: "source-toolbar" });
    const search = el("input", { class: "input", style: "max-width:260px;",
      placeholder: "按名称/URL筛选…" });
    search.oninput = () => { st.filter = search.value.trim().toLowerCase(); repaint(); };
    bar.appendChild(search);
    bar.appendChild(el("div", { class: "grow" }));
    bar.appendChild(el("button", { class: "btn btn-ghost", onclick: importBox },
      icon("import"), "导入"));
    bar.appendChild(el("button", { class: "btn btn-ghost", onclick: exportAll },
      icon("export"), "导出"));
    bar.appendChild(el("button", { class: "btn btn-primary", onclick: () => editSource(null) },
      icon("add"), "新建订阅源"));
    view.appendChild(bar);

    const wrap = el("div");
    view.appendChild(wrap);
    wrap.appendChild(loading("加载订阅源…"));
    try { st.sources = await api.getRssSources(); }
    catch (e) { st.sources = []; toast(e.message, "err"); }
    wrap.innerHTML = "";
    if (!st.sources.length) {
      wrap.appendChild(emptyState("暂无订阅源", "新建或导入订阅源 JSON。", "rss"));
      return;
    }
    wrap.appendChild(table());
  }

  function filtered() {
    if (!st.filter) return st.sources;
    return st.sources.filter((s) =>
      (s.sourceName + s.sourceUrl + (s.sourceGroup || ""))
        .toLowerCase().includes(st.filter));
  }

  function table() {
    const list = filtered();
    const t = el("table", { class: "source-table" });
    t.appendChild(el("thead", {}, el("tr", {},
      el("th", {}, "名称"), el("th", {}, "URL"), el("th", {}, "分组"),
      el("th", {}, "状态"), el("th", { style: "text-align:right" }, "操作"))));
    const tb = el("tbody", {});
    list.forEach((s) => {
      tb.appendChild(el("tr", {},
        el("td", { class: "src-name" }, esc(s.sourceName)),
        el("td", { class: "src-url", title: esc(s.sourceUrl) }, esc(s.sourceUrl)),
        el("td", { class: "src-group" }, esc(s.sourceGroup || "—")),
        el("td", {}, el("span", { class: "badge " + (s.enabled ? "on" : "off") },
          s.enabled ? "启用" : "禁用")),
        el("td", { class: "row-actions" },
          el("button", { class: "btn btn-sm btn-ghost", onclick: () => editSource(s) }, icon("edit")),
          el("button", { class: "btn btn-sm btn-danger", onclick: () => del(s) }, icon("delete")))));
    });
    t.appendChild(tb);
    return el("div", { class: "source-table-wrap" }, t);
  }

  function repaint() {
    const wrap = document.querySelector("#view .source-table-wrap");
    if (wrap) wrap.replaceWith(table());
  }

  function blankSource() {
    return {
      sourceUrl: "", sourceName: "", sourceGroup: "", sourceIcon: "",
      enabled: true, articleStyle: 0,
      ruleArticles: "", ruleTitle: "", ruleLink: "",
      ruleImage: "", ruleDescription: "", rulePubDate: "", ruleNextPage: "",
      ruleContent: "", header: "",
    };
  }

  function editSource(src) {
    const isNew = !src;
    const d = src ? JSON.parse(JSON.stringify(src)) : blankSource();
    const f = el("div", { class: "source-form" });
    const inp = (label, key, full, ph) => {
      const i = el("input", { class: "input", value: esc(d[key] || ""), placeholder: ph || "" });
      i.oninput = () => d[key] = i.value;
      return el("div", { class: "field" + (full ? " full" : "") },
        el("label", { class: "field-label" }, label), i);
    };
    f.appendChild(inp("源名称 *", "sourceName", false));
    f.appendChild(inp("源URL *", "sourceUrl", false));
    f.appendChild(inp("分组", "sourceGroup", false));
    f.appendChild(inp("图标URL", "sourceIcon", false));
    [
      ["ruleArticles", "列表规则"], ["ruleTitle", "标题规则"],
      ["ruleLink", "链接规则"], ["ruleImage", "图片规则"],
      ["ruleDescription", "描述规则"], ["rulePubDate", "发布日期规则"],
      ["ruleNextPage", "下一页规则"], ["ruleContent", "正文规则"],
      ["header", "请求头(JSON)"],
    ].forEach(([k, label]) => f.appendChild(inp(label, k, true)));
    const en = el("input", { type: "checkbox" }); en.checked = !!d.enabled;
    en.onchange = () => d.enabled = en.checked;
    f.appendChild(el("div", { class: "field full" },
      el("label", { class: "field-label" }, "启用"),
      el("label", { style: "display:flex;align-items:center;gap:6px;font-size:13px" },
        en, " 启用此订阅源")));

let mod;
    mod = modal({
      title: isNew ? "新建订阅源" : "编辑订阅源", wide: true, body: f,
      footer: [
        el("button", { class: "btn btn-ghost", onclick: () => mod.close() }, "取消"),
        el("button", { class: "btn btn-primary", onclick: save }, "保存"),
      ],
    });
    function save() {
      if (!d.sourceName || !d.sourceUrl) { toast("名称和URL不能为空", "err"); return; }
      api.saveRssSource(d).then(() => {
        mod.close(); toast("已保存", "ok"); render(document.getElementById("view"));
      }).catch((e) => toast(e.message, "err"));
    }
  }

  function del(s) {
    confirmBox(`删除订阅源「${s.sourceName}」？`, async () => {
      try { await api.deleteRssSources([s]); toast("已删除", "ok");
        render(document.getElementById("view")); }
      catch (e) { toast(e.message, "err"); }
    }, { danger: true, title: "删除订阅源" });
  }

  function importBox() {
    const ta = el("textarea", { class: "textarea", rows: "12",
      placeholder: "粘贴订阅源 JSON（对象或数组）…" });
let mod;
    mod = modal({ title: "导入订阅源", body: ta,
      footer: [
        el("button", { class: "btn btn-ghost", onclick: () => mod.close() }, "取消"),
        el("button", { class: "btn btn-primary", onclick: doImport }, "导入")] });
    async function doImport() {
      let arr;
      try { const v = JSON.parse(ta.value.trim()); arr = Array.isArray(v) ? v : [v]; }
      catch { toast("JSON 格式错误", "err"); return; }
      try {
        const res = await api.saveRssSources(arr);
        toast("成功导入 " + (Array.isArray(res) ? res.length : arr.length) + " 个订阅源", "ok");
        mod.close(); render(document.getElementById("view"));
      } catch (e) { toast(e.message, "err"); }
    }
  }

  function exportAll() {
    if (!st.sources.length) { toast("无可导出", "err"); return; }
    const blob = new Blob([JSON.stringify(st.sources, null, 2)],
      { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob),
      download: "legado_rss_sources.json" });
    document.body.appendChild(a); a.click(); a.remove();
    toast("已导出", "ok");
  }

  window.RssSourceView = { render };
})();
