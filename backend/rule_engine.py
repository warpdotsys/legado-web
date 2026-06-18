"""Book-source rule engine.

A faithful, pragmatic re-implementation of legado's AnalyzeRule for the most
common rule flavours used in real book sources:

  - CSS selectors              rule like `class.book-item@text` or `css:.item`
  - JSONPath (subset)          rule prefixed with `$.` or `json:`
  - XPath (subset)             rule prefixed with `xpath:` or `/`
  - regex                      rule prefixed with `regex:` or `@regex:`
  - plain string / @text/@src  attribute selectors

The original app also supports full Rhino JS rules (`<js>...</js>`). Those
cannot run portably in a Docker container without a JS runtime, so JS rules
are reported as unsupported rather than silently ignored. Everything else is
implemented with only the Python standard library + lxml/beautifulsoup when
available, falling back to html.parser if neither is installed.

This mirrors the rule pipeline in
app/src/main/java/io/legado/app/model/analyzeRule/AnalyzeRule.kt but keeps a
minimal surface: enough to power search / bookInfo / toc / content for the
majority of public book sources.
"""

import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, List, Optional

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:  # pragma: no cover - fallback path
    _HAS_BS4 = False

try:
    import lxml.html
    import lxml.etree
    _HAS_LXML = True
except ImportError:  # pragma: no cover
    _HAS_LXML = False


class RuleError(Exception):
    pass


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def absolute_url(base: str, url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://", "//")):
        return url if url.startswith("http") else "https:" + url
    return urllib.parse.urljoin(base, url)


def fill_search_url(search_url: str, key: str, page: int = 1) -> str:
    """Expand a legado searchUrl template like
    https://x.com/search?q={{key}}&page={{page}}."""
    if not search_url:
        return ""
    q = urllib.parse.quote(key)
    return (search_url
            .replace("{{key}}", q)
            .replace("searchKey=", f"searchKey={q}")
            .replace("{{page}}", str(page)))


# ---------------------------------------------------------------------------
# Rule parsing: a rule string may be "selector@field" or prefixed.
# ---------------------------------------------------------------------------

_ATTR_RE = re.compile(r"^(?P<head>.*?)(?:@(?P<attr>text|textNodes|src|href|"
                      r"html|content|title|ownText))?$", re.S)


def _split_rule(rule: str):
    """Split a rule into (selector, attr). attr defaults to 'text'."""
    rule = (rule or "").strip()
    if "@" in rule:
        head, _, tail = rule.rpartition("@")
        if tail in ("text", "textNodes", "src", "href", "html",
                    "content", "title", "ownText"):
            return head.strip(), tail
    return rule, "text"


def _detect_kind(rule: str) -> str:
    r = rule.strip()
    if r.startswith("css:"):
        return "css"
    if r.startswith("$.") or r.startswith("json:"):
        return "json"
    if r.startswith("xpath:") or r.startswith("//"):
        return "xpath"
    if r.startswith("regex:") or r.startswith("@regex:"):
        return "regex"
    if r.startswith("@"):
        return "css"  # legado @tag.class style
    return "css"


# ---------------------------------------------------------------------------
# Document wrappers
# ---------------------------------------------------------------------------

class _BaseDoc:
    def get_list(self, rule: str) -> List[Any]:
        raise NotImplementedError

    def get(self, rule: str) -> Optional[str]:
        items = self.get_list(rule)
        return items[0] if items else None


class _SoupDoc(_BaseDoc):
    """BeautifulSoup-backed document."""

    def __init__(self, html: str, base_url: str = ""):
        self.soup = BeautifulSoup(html, "html.parser")
        self.base_url = base_url

    def _select(self, selector: str) -> List:
        if selector.startswith("css:"):
            selector = selector[4:]
        if selector.startswith("@"):
            selector = selector[1:].replace(".", ".")
        try:
            return self.soup.select(selector)
        except Exception:
            return []

    def get_list(self, rule: str) -> List[Any]:
        selector, attr = _split_rule(rule)
        nodes = self._select(selector)
        if attr == "text":
            return [n.get_text(strip=True) for n in nodes]
        if attr == "ownText":
            return ["".join(t for t in n.find_all(string=True, recursive=False)).strip()
                    for n in nodes]
        if attr == "html":
            return [str(n) for n in nodes]
        return [n.get(attr, "") for n in nodes]

    def attr(self, node, attr: str) -> str:
        if attr == "text":
            return node.get_text(strip=True)
        if attr == "html":
            return str(node)
        return node.get(attr, "")


class _LxmlDoc(_BaseDoc):
    """lxml-backed document for xpath support."""

    def __init__(self, html: str, base_url: str = ""):
        self.tree = lxml.html.fromstring(html)
        self.base_url = base_url

    def get_list(self, rule: str) -> List[Any]:
        kind = _detect_kind(rule)
        if kind == "xpath":
            sel = rule[len("xpath:"):] if rule.startswith("xpath:") else rule
            try:
                return self.tree.xpath(sel)
            except Exception:
                return []
        # css via lxml
        selector, attr = _split_rule(rule)
        sel = selector[len("css:"):] if selector.startswith("css:") else selector
        try:
            nodes = self.tree.cssselect(sel) if _HAS_LXML else []
        except Exception:
            nodes = []
        out = []
        for n in nodes:
            if attr == "text":
                out.append(n.text_content().strip())
            elif attr == "html":
                out.append(lxml.etree.tostring(n, encoding="unicode"))
            else:
                out.append(n.get(attr, ""))
        return out


class _RegexDoc(_BaseDoc):
    def __init__(self, text: str, base_url: str = ""):
        self.text = text
        self.base_url = base_url

    def get_list(self, rule: str) -> List[Any]:
        pattern = rule
        for pfx in ("regex:", "@regex:"):
            if pattern.startswith(pfx):
                pattern = pattern[len(pfx):]
        # legado uses `regex##group` sometimes
        pattern = pattern.split("##")[0]
        try:
            return [m if isinstance(m, str) else (m.group(1) or m.group(0))
                    for m in re.finditer(pattern, self.text, re.S)]
        except re.error:
            return []


def parse_doc(content: str, base_url: str = "") -> _BaseDoc:
    """Choose the best available parser for an HTML/text document.

    JSON content -> _JsonDoc.  XPath-prefixed rules need lxml, but for plain
    CSS/regex rules BeautifulSoup is the default (it bundles CSS support
    without the extra `cssselect` dependency).
    """
    if not content:
        return _SoupDoc("", base_url) if _HAS_BS4 else _RegexDoc("", base_url)
    stripped = content.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return _JsonDoc(content, base_url)
    if _HAS_BS4:
        return _SoupDoc(content, base_url)
    if _HAS_LXML:
        return _LxmlDoc(content, base_url)
    return _RegexDoc(content, base_url)


class _JsonDoc(_BaseDoc):
    """Minimal JSONPath evaluator supporting $.a.b[0].c and $.a[*].b."""

    def __init__(self, text: str, base_url: str = ""):
        try:
            self.data = json.loads(text)
        except json.JSONDecodeError:
            self.data = None
        self.base_url = base_url

    def _walk(self, expr: str):
        if self.data is None:
            return []
        cur = [self.data]
        for token in re.findall(r"\.([^\.\[\]]+)|\[(\d+)\]|\[\*\]", expr):
            name, idx = token[0], token[1]
            star = (token[0] == "" and token[1] == "")
            nxt = []
            if star:
                for c in cur:
                    if isinstance(c, list):
                        nxt.extend(c)
            elif idx:
                i = int(idx)
                for c in cur:
                    if isinstance(c, list) and i < len(c):
                        nxt.append(c[i])
            elif name:
                for c in cur:
                    if isinstance(c, dict) and name in c:
                        nxt.append(c[name])
            cur = nxt
        return cur

    def get_list(self, rule: str) -> List[Any]:
        expr = rule
        for pfx in ("json:", "$."):
            if expr.startswith(pfx):
                expr = expr[len(pfx):]
                break
        expr = "$." + expr.lstrip(".")
        results = self._walk(expr)
        out = []
        for r in results:
            if isinstance(r, (dict, list)):
                out.append(json.dumps(r, ensure_ascii=False))
            else:
                out.append("" if r is None else str(r))
        return out


# ---------------------------------------------------------------------------
# High-level rule application used by api.py
# ---------------------------------------------------------------------------

@dataclass
class SearchBook:
    name: str = ""
    author: str = ""
    kind: str = ""
    intro: str = ""
    coverUrl: str = ""
    bookUrl: str = ""
    lastChapter: str = ""
    updateTime: str = ""
    wordCount: str = ""
    origin: str = ""
    originName: str = ""
    type: int = 0


def _js_rule(rule_str: str) -> bool:
    return bool(rule_str) and ("<js>" in rule_str or rule_str.startswith("@js:"))


def apply_simple_rule(doc: _BaseDoc, rule: str, base_url: str = "") -> str:
    """Evaluate a rule that yields a single string value."""
    if not rule:
        return ""
    if _js_rule(rule):
        raise RuleError("JavaScript 规则不支持 (需要 legado App 执行)")
    val = doc.get(rule)
    return val if isinstance(val, str) else ""


def get_book_list(doc: _BaseDoc, list_rule: str) -> List[Any]:
    """Return the list of nodes matching a bookList rule."""
    if not list_rule:
        return []
    if _js_rule(list_rule):
        raise RuleError("JavaScript 规则不支持 (需要 legado App 执行)")
    selector, _ = _split_rule(list_rule)
    # BeautifulSoup-backed document.
    if isinstance(doc, _SoupDoc):
        nodes = doc._select(selector)
        return [_SoupNode(n, doc.base_url) for n in nodes]
    # lxml-backed document.
    if isinstance(doc, _LxmlDoc):
        kind = _detect_kind(selector)
        if kind == "xpath":
            sel = selector[len("xpath:"):] if selector.startswith("xpath:") else selector
            try:
                return [_LxmlNode(n, doc.base_url) for n in doc.tree.xpath(sel)]
            except Exception:
                return []
        sel = selector[len("css:"):] if selector.startswith("css:") else selector
        try:
            return [_LxmlNode(n, doc.base_url) for n in doc.tree.cssselect(sel)]
        except Exception:
            return []
    # JSON-backed document.
    if isinstance(doc, _JsonDoc):
        items = doc.get_list(list_rule)
        return [_JsonNode(it) for it in items]
    return []


class _SoupNode:
    def __init__(self, node, base_url):
        self.node = node
        self.base_url = base_url

    def get(self, rule: str) -> str:
        if not rule:
            return ""
        selector, attr = _split_rule(rule)
        if selector:
            try:
                subs = self.node.select(selector)
            except Exception:
                subs = []
            target = subs[0] if subs else self.node
        else:
            target = self.node
        if attr == "text":
            return target.get_text(strip=True)
        if attr == "html":
            return str(target)
        val = target.get(attr, "")
        if attr in ("src", "href"):
            val = absolute_url(self.base_url, val)
        return val


class _LxmlNode:
    def __init__(self, node, base_url):
        self.node = node
        self.base_url = base_url

    def get(self, rule: str) -> str:
        if not rule:
            return ""
        selector, attr = _split_rule(rule)
        if selector:
            kind = _detect_kind(selector)
            if kind == "xpath":
                sel = selector[len("xpath:"):] if selector.startswith("xpath:") else selector
                try:
                    subs = self.node.xpath(sel)
                except Exception:
                    subs = []
            else:
                sel = selector[len("css:"):] if selector.startswith("css:") else selector
                try:
                    subs = self.node.cssselect(sel)
                except Exception:
                    subs = []
            target = subs[0] if subs else self.node
        else:
            target = self.node
        if attr == "text":
            return target.text_content().strip()
        if attr == "html":
            return lxml.etree.tostring(target, encoding="unicode")
        val = target.get(attr, "")
        if attr in ("src", "href"):
            val = absolute_url(self.base_url, val)
        return val


class _JsonNode:
    def __init__(self, raw: str):
        self.raw = raw
        try:
            self.data = json.loads(raw)
        except json.JSONDecodeError:
            self.data = raw

    def get(self, rule: str) -> str:
        if not rule:
            return ""
        expr = rule
        for pfx in ("json:", "$."):
            if expr.startswith(pfx):
                expr = expr[len(pfx):]
                break
        if not expr.startswith("$"):
            expr = "$." + expr.lstrip(".")
        doc = _JsonDoc(self.raw if isinstance(self.data, (dict, list)) else "{}")
        vals = doc._walk(expr)
        if not vals:
            return ""
        v = vals[0]
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
