/* Replace rules management: list / add / edit / delete / test */
(function () {
  "use strict";
  const { el, icon, esc, toast, modal, confirmBox, loading, emptyState } = window.UI;
  const api = window.LegadoAPI;

  let st = { rules: [] };

  async function render(view) {
    view.innerHTML = "";
    const countEl = el("span", { class: "count" }, "… 条");
    view.appendChild(el("div", { class: "page-head" },
      el("div", { class: "page-title" }, icon("replace"), "替换净化规则",
        countEl)));

    const bar = el("div", { class: "source-toolbar" });
    bar.appendChild(el("div", { class: "grow" }));
    bar.appendChild(el("button", { class: "btn btn-primary", onclick: () => edit(null) },
      icon("add"), "新建规则"));
    view.appendChild(bar);

    const wrap = el("div");
    view.appendChild(wrap);
    wrap.appendChild(loading("加载规则…"));
    try { st.rules = await api.getReplaceRules(); }
    catch (e) { st.rules = []; toast(e.message, "err"); }
    // rules may come back as a JSON string
    if (typeof st.rules === "string") {
      try { st.rules = JSON.parse(st.rules); } catch { st.rules = []; }
    }
    countEl.textContent = st.rules.length + " 条";
    wrap.innerHTML = "";
    if (!st.rules.length) {
      wrap.appendChild(emptyState("暂无替换规则", "新建规则可净化正文，例如去除广告文字。", "replace"));
      return;
    }
    wrap.appendChild(list());
  }

  function list() {
    const box = el("div", { class: "rule-list" });
    st.rules.forEach((r) => {
      box.appendChild(el("div", { class: "rule-card" },
        el("div", { class: "rule-name", title: esc(r.name) }, esc(r.name || "未命名")),
        el("div", { class: "rule-pattern", title: esc(r.pattern) },
          r.isRegex ? "[正则] " : "", esc(r.pattern || "—")),
        el("span", { style: "color:var(--text-dim)" }, "→"),
        el("div", { class: "rule-repl", title: esc(r.replacement) },
          esc(r.replacement || "(删除)")),
        el("span", { class: "badge " + (r.isEnabled ? "on" : "off") },
          r.isEnabled ? "启用" : "禁用"),
        el("div", { class: "row-actions" },
          el("button", { class: "btn btn-sm btn-ghost", onclick: () => test(r) }, icon("debug"), "测试"),
          el("button", { class: "btn btn-sm btn-ghost", onclick: () => edit(r) }, icon("edit")),
          el("button", { class: "btn btn-sm btn-danger", onclick: () => del(r) }, icon("delete")))));
    });
    return box;
  }

  function edit(src) {
    const isNew = !src;
    const d = src ? JSON.parse(JSON.stringify(src)) : {
      name: "", pattern: "", replacement: "", isRegex: false,
      isEnabled: true, scopeContent: true, scopeTitle: false, order: -2147483648,
    };
    const f = el("div", { class: "source-form" });
    const inp = (label, key, full) => {
      const i = el("input", { class: "input", value: esc(d[key] || "") });
      i.oninput = () => d[key] = i.value;
      return el("div", { class: "field" + (full ? " full" : "") },
        el("label", { class: "field-label" }, label), i);
    };
    f.appendChild(inp("名称", "name", true));
    f.appendChild(inp("匹配内容", "pattern", true));
    f.appendChild(inp("替换为(空=删除)", "replacement", true));
    f.appendChild(inp("作用范围", "scope", true));
    const reg = el("input", { type: "checkbox" }); reg.checked = !!d.isRegex;
    reg.onchange = () => d.isRegex = reg.checked;
    const en = el("input", { type: "checkbox" }); en.checked = !!d.isEnabled;
    en.onchange = () => d.isEnabled = en.checked;
    f.appendChild(el("div", { class: "field full" },
      el("label", { class: "field-label" }, "选项"),
      el("label", { style: "display:flex;gap:16px;font-size:13px" },
        el("label", {}, reg, " 正则模式"),
        el("label", {}, en, " 启用"))));

let mod;
    mod = modal({
      title: isNew ? "新建替换规则" : "编辑替换规则", body: f,
      footer: [
        el("button", { class: "btn btn-ghost", onclick: () => mod.close() }, "取消"),
        el("button", { class: "btn btn-primary", onclick: save }, "保存")] });
    function save() {
      if (!d.pattern) { toast("匹配内容不能为空", "err"); return; }
      api.saveReplaceRule(d).then(() => {
        mod.close(); toast("已保存", "ok"); render(document.getElementById("view"));
      }).catch((e) => toast(e.message, "err"));
    }
  }

  function test(r) {
    const textIn = el("textarea", { class: "textarea", rows: "5",
      placeholder: "粘贴要测试的文本…" });
    const out = el("div", { class: "debug-console", style: "min-height:80px" },
      "替换结果将显示于此…");
let mod;
    mod = modal({
      title: "测试规则 — " + (r.name || "未命名"), wide: true,
      body: [textIn, el("div", { class: "mt-16" },
        el("label", { class: "field-label" }, "结果")), out],
      footer: [
        el("button", { class: "btn btn-ghost", onclick: () => mod.close() }, "关闭"),
        el("button", { class: "btn btn-primary", onclick: run }, "运行测试")] });
    async function run() {
      if (!textIn.value) { toast("请输入测试文本", "err"); return; }
      out.textContent = "测试中…";
      try {
        const res = await api.testReplaceRule(r, textIn.value);
        out.textContent = res || "(替换结果为空)";
      } catch (e) { out.innerHTML = '<span class="line-err">' + esc(e.message) + "</span>"; }
    }
  }

  function del(r) {
    confirmBox(`删除规则「${r.name || "未命名"}」？`, async () => {
      try { await api.deleteReplaceRule(r); toast("已删除", "ok");
        render(document.getElementById("view")); }
      catch (e) { toast(e.message, "err"); }
    }, { danger: true, title: "删除规则" });
  }

  window.ReplaceRuleView = { render };
})();
