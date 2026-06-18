"""HTTP fetching + book-source execution pipeline.

Implements the search / bookInfo / chapterList / content flow used by the
legado web API, mirroring io.legado.app.model.webBook.WebBook.
"""

import json
import time
import urllib.request
import urllib.parse
import gzip
import io
from typing import List, Optional

from models import Book, BookSource, BookChapter
from database import BookDao, BookSourceDao, BookChapterDao
from rule_engine import (
    parse_doc, get_book_list, apply_simple_rule, SearchBook,
    fill_search_url, absolute_url, RuleError,
)


DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def parse_headers(header_str: str) -> dict:
    headers = {"User-Agent": DEFAULT_UA}
    if not header_str:
        return headers
    try:
        obj = json.loads(header_str)
        if isinstance(obj, dict):
            for k, v in obj.items():
                headers[str(k)] = str(v)
            return headers
    except json.JSONDecodeError:
        pass
    for line in header_str.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, _, v = line.partition(":")
        headers[k.strip()] = v.strip()
    return headers


def http_get(url: str, source: Optional[BookSource] = None,
             timeout: int = 20) -> str:
    headers = parse_headers(source.header if source else "")
    if "User-Agent" not in headers:
        headers["User-Agent"] = DEFAULT_UA
    headers.setdefault("Accept", "*/*")
    headers.setdefault("Accept-Encoding", "gzip, deflate")
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        charset = resp.headers.get_content_charset() or "utf-8"
        try:
            return data.decode(charset, errors="replace")
        except LookupError:
            return data.decode("utf-8", errors="replace")


def _source_headers(source: BookSource) -> dict:
    return parse_headers(source.header)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_book(source: BookSource, key: str, page: int = 1) -> List[SearchBook]:
    if not source.searchUrl:
        raise RuleError(f"书源 {source.bookSourceName} 未配置搜索URL")
    url = fill_search_url(source.searchUrl, key, page)
    html = http_get(url, source)
    doc = parse_doc(html, url)
    rule = source.ruleSearch
    if not rule:
        return []
    nodes = get_book_list(doc, rule.bookList or "")
    results: List[SearchBook] = []
    for node in nodes:
        try:
            name = node.get(rule.name or "") if rule.name else ""
            author = node.get(rule.author or "") if rule.author else ""
            book_url_raw = node.get(rule.bookUrl or "") if rule.bookUrl else ""
            book_url = absolute_url(url, book_url_raw)
            cover_raw = node.get(rule.coverUrl or "") if rule.coverUrl else ""
            results.append(SearchBook(
                name=name, author=author,
                kind=node.get(rule.kind or "") if rule.kind else "",
                intro=node.get(rule.intro or "") if rule.intro else "",
                coverUrl=absolute_url(url, cover_raw),
                bookUrl=book_url,
                lastChapter=node.get(rule.lastChapter or "") if rule.lastChapter else "",
                updateTime=node.get(rule.updateTime or "") if rule.updateTime else "",
                wordCount=node.get(rule.wordCount or "") if rule.wordCount else "",
                origin=source.bookSourceUrl,
                originName=source.bookSourceName,
                type=source.bookSourceType,
            ))
        except RuleError:
            continue
    return results


# ---------------------------------------------------------------------------
# Book info
# ---------------------------------------------------------------------------

def get_book_info(source: BookSource, book: Book) -> Book:
    html = http_get(book.bookUrl, source)
    doc = parse_doc(html, book.bookUrl)
    rule = source.ruleBookInfo
    if not rule:
        return book
    if rule.name:
        book.name = doc.get(rule.name) or book.name
    if rule.author:
        book.author = doc.get(rule.author) or book.author
    if rule.intro:
        book.intro = doc.get(rule.intro) or book.intro
    if rule.kind:
        book.kind = doc.get(rule.kind) or book.kind
    if rule.coverUrl:
        book.coverUrl = absolute_url(book.bookUrl, doc.get(rule.coverUrl) or "")
    if rule.lastChapter:
        book.latestChapterTitle = doc.get(rule.lastChapter) or book.latestChapterTitle
    if rule.wordCount:
        book.wordCount = doc.get(rule.wordCount) or book.wordCount
    if rule.tocUrl:
        toc_raw = doc.get(rule.tocUrl) or ""
        book.tocUrl = absolute_url(book.bookUrl, toc_raw)
    else:
        book.tocUrl = book.bookUrl
    return book


# ---------------------------------------------------------------------------
# Chapter list
# ---------------------------------------------------------------------------

def get_chapter_list(source: BookSource, book: Book) -> List[BookChapter]:
    toc_url = book.tocUrl or book.bookUrl
    html = http_get(toc_url, source)
    doc = parse_doc(html, toc_url)
    rule = source.ruleToc
    if not rule:
        return []
    nodes = get_book_list(doc, rule.chapterList or "")
    chapters: List[BookChapter] = []
    for idx, node in enumerate(nodes):
        title = node.get(rule.chapterName or "") if rule.chapterName else ""
        if not title:
            continue
        chapter_url_raw = node.get(rule.chapterUrl or "") if rule.chapterUrl else ""
        chapter_url = absolute_url(toc_url, chapter_url_raw)
        chapters.append(BookChapter(
            url=chapter_url, title=title,
            isVolume=bool(node.get(rule.isVolume or "")) if rule.isVolume else False,
            isVip=bool(node.get(rule.isVip or "")) if rule.isVip else False,
            baseUrl=toc_url, bookUrl=book.bookUrl, index=idx,
            tag=node.get(rule.updateTime or "") if rule.updateTime else None,
        ))
    # follow nextTocUrl (paginated chapter lists)
    next_rule = rule.nextTocUrl
    if next_rule:
        seen = {toc_url}
        guard = 0
        while guard < 20:
            guard += 1
            next_raw = doc.get(next_rule) if hasattr(doc, "get") else ""
            if not next_raw:
                break
            next_url = absolute_url(toc_url, next_raw)
            if next_url in seen or not next_url:
                break
            seen.add(next_url)
            try:
                html2 = http_get(next_url, source)
            except Exception:
                break
            doc2 = parse_doc(html2, next_url)
            nodes2 = get_book_list(doc2, rule.chapterList or "")
            for node in nodes2:
                title = node.get(rule.chapterName or "") if rule.chapterName else ""
                if not title:
                    continue
                chapter_url_raw = node.get(rule.chapterUrl or "") if rule.chapterUrl else ""
                chapters.append(BookChapter(
                    url=absolute_url(next_url, chapter_url_raw),
                    title=title, baseUrl=next_url, bookUrl=book.bookUrl,
                    index=len(chapters),
                ))
            toc_url = next_url
            doc = doc2
    return chapters


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def get_content(source: BookSource, book: Book, chapter: BookChapter) -> str:
    html = http_get(chapter.url, source)
    doc = parse_doc(html, chapter.url)
    rule = source.ruleContent
    if not rule or not rule.content:
        return ""
    content = doc.get(rule.content) or ""
    # Apply replaceRegex if present in the rule.
    if rule.replaceRegex:
        content = _apply_replace_regex(content, rule.replaceRegex)
    return content


def _apply_replace_regex(content: str, spec: str) -> str:
    """spec like `pattern##replacement` (legado format)."""
    parts = spec.split("##")
    pattern = parts[0]
    replacement = parts[1] if len(parts) > 1 else ""
    try:
        return re.sub(pattern, replacement, content)
    except re.error:
        return content


import re  # noqa: E402  (kept here to avoid cluttering the top)
