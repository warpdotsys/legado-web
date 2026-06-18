/* About view */
(function () {
  "use strict";
  const { el, icon, esc } = window.UI;

  async function render(view) {
    view.innerHTML = "";
    view.appendChild(el("div", { class: "page-head" },
      el("div", { class: "page-title" }, icon("about"), "关于")));

    const panel = el("div", { class: "panel", style: "max-width:680px" });
    panel.appendChild(el("div", { class: "panel-head" },
      el("div", { class: "modal-title" }, "阅读 Web · Docker 移植版")));
    const body = el("div", { class: "panel-body" });

    body.appendChild(el("p", { style: "margin-bottom:12px;color:var(--text-soft)" },
      "本项目将安卓阅读 App（legado）移植到 Docker 平台：保留了原 App 内置的 Web 服务（端口 1122，" +
      "提供完整的 legado JSON API 与 WebSocket 调试/搜索接口），并将 App 界面转换为原生 Web 界面，" +
      "可在浏览器中完成书架、阅读、书源管理、订阅源管理、替换净化、在线搜索等全部操作。"));

    const rows = [
      ["后端服务端口", "1122 (HTTP API + Web UI)"],
      ["WebSocket 端口", "1123 (searchBook / bookSourceDebug / rssSourceDebug)"],
      ["数据存储", "SQLite（容器卷 /data/legado.db）"],
      ["API 兼容", "完全兼容 legado HttpServer.kt 的全部接口与 ReturnData 格式"],
      ["规则引擎", "CSS 选择器 / XPath / JSONPath / 正则（JS 规则需 legado App 执行）"],
      ["上游项目", "github.com/warpdotsys/legado"],
    ];
    const tbl = el("table", { class: "table" });
    rows.forEach(([k, v]) => tbl.appendChild(el("tr", {},
      el("td", { style: "width:140px;font-weight:600;color:var(--text-soft)" }, k),
      el("td", { class: "text-mono" }, esc(v)))));
    body.appendChild(tbl);

    body.appendChild(el("hr", { class: "divider" }));
    body.appendChild(el("p", { style: "font-size:13px;color:var(--text-dim)" },
      "免责声明：本服务不提供任何书籍内容，需自行添加书源。请遵守当地法律法规，仅供学习交流使用。"));

    panel.appendChild(body);
    view.appendChild(panel);
  }

  window.AboutView = { render };
})();
