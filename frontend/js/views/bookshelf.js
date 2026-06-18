/* Bookshelf view */
(function () {
  "use strict";
  const { el, icon, esc, loading, emptyState, toast } = window.UI;
  const api = window.LegadoAPI;

  async function render(view) {
    view.appendChild(loading("加载书架…"));
    let books = [];
    try {
      books = await api.getBookshelf();
    } catch (e) {
      view.innerHTML = "";
      view.appendChild(emptyState("书架为空", e.message, "book"));
      return;
    }
    view.innerHTML = "";

    const head = el("div", { class: "page-head" },
      el("div", { class: "page-title" }, icon("book"), "书架",
        el("span", { class: "count" }, books.length + " 本")),
      el("div", { class: "row" },
        el("button", { class: "btn btn-ghost btn-sm", onclick: () => load() },
          icon("refresh"), "刷新")));
    view.appendChild(head);

    if (!books.length) {
      view.appendChild(emptyState("书架还是空的", "去「搜索」页找几本书加入书架吧。", "search"));
      return;
    }

    const shelf = el("div", { class: "shelf" });
    books.forEach((b) => shelf.appendChild(bookCard(b, () => load())));
    view.appendChild(shelf);
  }

  function bookCard(b, reload) {
    const cover = el("div", { class: "book-cover" });
    if (b.coverUrl) {
      const img = el("img", { alt: b.name, src: api.coverUrl(b.coverUrl) });
      img.addEventListener("error", () => {
        img.remove();
        cover.appendChild(el("div", { class: "cover-fallback" }, esc(b.name)));
      });
      cover.appendChild(img);
    } else {
      cover.appendChild(el("div", { class: "cover-fallback" }, esc(b.name)));
    }
    if (b.totalChapterNum > 0)
      cover.appendChild(el("span", { class: "cover-badge" }, b.totalChapterNum + "章"));

    const card = el("div", { class: "book-card", title: b.name },
      cover,
      el("div", { class: "book-meta" },
        el("div", { class: "book-name" }, esc(b.name)),
        el("div", { class: "book-author" }, esc(b.author || "")),
        b.latestChapterTitle
          ? el("div", { class: "book-latest", title: esc(b.latestChapterTitle) },
              esc(b.latestChapterTitle))
          : null));
    card.addEventListener("click", () => {
      location.hash = "#/read/" + encodeURIComponent(b.bookUrl);
    });
    card.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      window.UI.confirmBox(`从书架移除《${b.name}》？`, async () => {
        try { await api.deleteBook(b); toast("已移除", "ok"); reload(); }
        catch (err) { toast(err.message, "err"); }
      }, { danger: true, title: "移除书籍" });
    });
    return card;
  }

  async function load() {
    const view = document.getElementById("view");
    view.innerHTML = "";
    view.classList.remove("view-enter");
    void view.offsetWidth;
    view.classList.add("view-enter");
    await render(view);
  }

  window.BookshelfView = { render: load };
})();
