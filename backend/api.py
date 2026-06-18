"""API controllers — direct port of
app/src/main/java/io/legado/app/api/controller/*.

Each method returns a ReturnData dict {isSuccess, errorMsg, data} exactly like
the Android HttpServer responses, so legado's own web clients keep working.
"""

import json
import time
import re
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from models import (
    Book, BookSource, RssSource, ReplaceRule, BookChapter, BookProgress,
)
from database import (
    BookDao, BookSourceDao, RssSourceDao, ReplaceRuleDao,
    BookChapterDao, ReadConfigDao,
)
from book_engine import (
    search_book, get_book_info, get_chapter_list, get_content,
)
from models import _asdict
from rule_engine import RuleError


class ReturnData:
    def __init__(self):
        self.isSuccess = False
        self.errorMsg = "未知错误,请联系开发者!"
        self.data: Any = None

    def set_error_msg(self, msg: str) -> "ReturnData":
        self.isSuccess = False
        self.errorMsg = msg
        return self

    def set_data(self, data: Any) -> "ReturnData":
        self.isSuccess = True
        self.errorMsg = ""
        self.data = data
        return self

    def to_dict(self) -> dict:
        return {
            "isSuccess": self.isSuccess,
            "errorMsg": self.errorMsg,
            "data": _asdict(self.data),
        }


def _parse_json(raw: Optional[str]):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _book_from_dict(d: dict) -> Book:
    valid = {f for f in Book.__dataclass_fields__}
    return Book(**{k: v for k, v in d.items() if k in valid})


def _source_from_dict(d: dict) -> BookSource:
    valid = {f for f in BookSource.__dataclass_fields__}
    return BookSource(**{k: v for k, v in d.items() if k in valid})


def _rss_from_dict(d: dict) -> RssSource:
    valid = {f for f in RssSource.__dataclass_fields__}
    return RssSource(**{k: v for k, v in d.items() if k in valid})


def _replace_from_dict(d: dict) -> ReplaceRule:
    valid = {f for f in ReplaceRule.__dataclass_fields__}
    return ReplaceRule(**{k: v for k, v in d.items() if k in valid})


# ---------------------------------------------------------------------------
# BookController
# ---------------------------------------------------------------------------

class BookController:
    @staticmethod
    def bookshelf() -> ReturnData:
        books = BookDao.all()
        rd = ReturnData()
        if not books:
            return rd.set_error_msg("还没有添加小说")
        data = sorted(books, key=lambda b: b.durChapterTime, reverse=True)
        return rd.set_data(data)

    @staticmethod
    def get_chapter_list(params: Dict[str, List[str]]) -> ReturnData:
        rd = ReturnData()
        book_url = (params.get("url") or [""])[0]
        if not book_url:
            return rd.set_error_msg("参数url不能为空，请指定书籍地址")
        chapters = BookChapterDao.get_chapter_list(book_url)
        if chapters:
            return rd.set_data(chapters)
        return BookController.refresh_toc(params)

    @staticmethod
    def refresh_toc(params: Dict[str, List[str]]) -> ReturnData:
        rd = ReturnData()
        book_url = (params.get("url") or [""])[0]
        if not book_url:
            return rd.set_error_msg("参数url不能为空，请指定书籍地址")
        book = BookDao.get_book(book_url)
        if not book:
            return rd.set_error_msg("未在数据库找到对应书籍，请先添加")
        source = BookSourceDao.get_book_source(book.origin)
        if not source:
            return rd.set_error_msg("未找到对应书源,请换源")
        try:
            toc = get_chapter_list(source, book)
        except RuleError as e:
            return rd.set_error_msg(str(e))
        except Exception as e:
            return rd.set_error_msg(f"refresh toc error: {e}")
        BookChapterDao.replace_all(book.bookUrl, toc)
        book.totalChapterNum = len(toc)
        book.lastCheckTime = int(time.time() * 1000)
        BookDao.update(book)
        return rd.set_data(toc)

    @staticmethod
    def get_book_content(params: Dict[str, List[str]]) -> ReturnData:
        rd = ReturnData()
        book_url = (params.get("url") or [""])[0]
        index_raw = (params.get("index") or [""])[0]
        if not book_url:
            return rd.set_error_msg("参数url不能为空，请指定书籍地址")
        if not index_raw:
            return rd.set_error_msg("参数index不能为空, 请指定目录序号")
        try:
            index = int(index_raw)
        except ValueError:
            return rd.set_error_msg("参数index必须为数字")
        book = BookDao.get_book(book_url)
        if not book:
            return rd.set_error_msg("未找到书籍")
        chapter = BookChapterDao.get_chapter(book_url, index)
        if not chapter:
            return rd.set_error_msg("未找到章节")
        source = BookSourceDao.get_book_source(book.origin)
        if not source:
            return rd.set_error_msg("未找到书源")
        try:
            content = get_content(source, book, chapter)
        except RuleError as e:
            return rd.set_error_msg(str(e))
        except Exception as e:
            return rd.set_error_msg(f"获取正文失败: {e}")
        return rd.set_data(content)

    @staticmethod
    def save_book(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        d = _parse_json(post_data)
        if not d:
            return rd.set_error_msg("格式不对")
        book = _book_from_dict(d)
        if not book.bookUrl:
            book.bookUrl = book.name + "|" + book.author
        BookDao.insert(book)
        return rd.set_data("")

    @staticmethod
    def delete_book(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        d = _parse_json(post_data)
        if not d:
            return rd.set_error_msg("格式不对")
        book = _book_from_dict(d)
        BookDao.delete(book)
        BookChapterDao.del_by_book(book.bookUrl)
        return rd.set_data("")

    @staticmethod
    def save_book_progress(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        d = _parse_json(post_data)
        if not d:
            return rd.set_error_msg("格式不对")
        name = d.get("name", "")
        author = d.get("author", "")
        book = BookDao.get_book_by_name(name, author)
        if not book:
            return rd.set_error_msg("未找到书籍")
        book.durChapterIndex = int(d.get("durChapterIndex", 0))
        book.durChapterPos = int(d.get("durChapterPos", 0))
        book.durChapterTime = int(d.get("durChapterTime", 0))
        book.durChapterTitle = d.get("durChapterTitle")
        BookDao.update(book)
        return rd.set_data("")

    @staticmethod
    def get_cover(params: Dict[str, List[str]]) -> ReturnData:
        # Covers are remote URLs in this port; the frontend proxies them
        # directly. Return the URL so callers can fetch it themselves.
        rd = ReturnData()
        path = (params.get("path") or [""])[0]
        if not path:
            return rd.set_error_msg("path为空")
        return rd.set_data(path)

    @staticmethod
    def get_img(params: Dict[str, List[str]]) -> ReturnData:
        rd = ReturnData()
        src = (params.get("path") or [""])[0]
        if not src:
            return rd.set_error_msg("图片链接为空")
        return rd.set_data(src)

    @staticmethod
    def get_web_read_config() -> ReturnData:
        rd = ReturnData()
        return rd.set_data(ReadConfigDao.get())

    @staticmethod
    def save_web_read_config(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        if post_data is None:
            return rd.set_error_msg("数据不能为空")
        # Accept either a JSON string or an already-parsed object.
        if isinstance(post_data, (dict, list)):
            value = json.dumps(post_data, ensure_ascii=False)
        else:
            value = post_data
        try:
            json.loads(value)
        except json.JSONDecodeError:
            return rd.set_error_msg("配置不是合法JSON")
        ReadConfigDao.save(value)
        return rd.set_data("")


# ---------------------------------------------------------------------------
# BookSourceController
# ---------------------------------------------------------------------------

class BookSourceController:
    @staticmethod
    def sources() -> ReturnData:
        rd = ReturnData()
        srcs = BookSourceDao.all()
        if not srcs:
            return rd.set_error_msg("设备源列表为空")
        return rd.set_data(srcs)

    @staticmethod
    def get_source(params: Dict[str, List[str]]) -> ReturnData:
        rd = ReturnData()
        url = (params.get("url") or [""])[0]
        if not url:
            return rd.set_error_msg("参数url不能为空，请指定源地址")
        src = BookSourceDao.get_book_source(url)
        if not src:
            return rd.set_error_msg("未找到源，请检查书源地址")
        return rd.set_data(src)

    @staticmethod
    def save_source(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        d = _parse_json(post_data)
        if d is None:
            return rd.set_error_msg("数据不能为空")
        src = _source_from_dict(d)
        if not src.bookSourceName or not src.bookSourceUrl:
            return rd.set_error_msg("源名称和URL不能为空")
        src.lastUpdateTime = int(time.time() * 1000)
        BookSourceDao.insert(src)
        return rd.set_data("")

    @staticmethod
    def save_sources(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        arr = _parse_json(post_data)
        if not isinstance(arr, list):
            return rd.set_error_msg("转换源失败")
        ok = []
        for d in arr:
            src = _source_from_dict(d)
            if src.bookSourceName and src.bookSourceUrl:
                src.lastUpdateTime = int(time.time() * 1000)
                BookSourceDao.insert(src)
                ok.append(src)
        return rd.set_data(ok)

    @staticmethod
    def delete_sources(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        arr = _parse_json(post_data)
        if not isinstance(arr, list):
            return rd.set_error_msg("数据格式错误")
        for d in arr:
            url = d.get("bookSourceUrl") if isinstance(d, dict) else None
            if url:
                BookSourceDao.delete(url)
        return rd.set_data("已执行")


# ---------------------------------------------------------------------------
# RssSourceController
# ---------------------------------------------------------------------------

class RssSourceController:
    @staticmethod
    def sources() -> ReturnData:
        rd = ReturnData()
        srcs = RssSourceDao.all()
        if not srcs:
            return rd.set_error_msg("源列表为空")
        return rd.set_data(srcs)

    @staticmethod
    def get_source(params: Dict[str, List[str]]) -> ReturnData:
        rd = ReturnData()
        url = (params.get("url") or [""])[0]
        if not url:
            return rd.set_error_msg("参数url不能为空，请指定源地址")
        src = RssSourceDao.get_source(url)
        if not src:
            return rd.set_error_msg("未找到源，请检查订阅源地址")
        return rd.set_data(src)

    @staticmethod
    def save_source(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        d = _parse_json(post_data)
        if d is None:
            return rd.set_error_msg("数据不能为空")
        src = _rss_from_dict(d)
        if not src.sourceName or not src.sourceUrl:
            return rd.set_error_msg("源名称和URL不能为空")
        src.lastUpdateTime = int(time.time() * 1000)
        RssSourceDao.insert(src)
        return rd.set_data("")

    @staticmethod
    def save_sources(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        arr = _parse_json(post_data)
        if not isinstance(arr, list):
            return rd.set_error_msg("转换源失败")
        ok = []
        for d in arr:
            src = _rss_from_dict(d)
            if src.sourceName and src.sourceUrl:
                src.lastUpdateTime = int(time.time() * 1000)
                RssSourceDao.insert(src)
                ok.append(src)
        return rd.set_data(ok)

    @staticmethod
    def delete_sources(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        arr = _parse_json(post_data)
        if not isinstance(arr, list):
            return rd.set_error_msg("数据格式错误")
        for d in arr:
            url = d.get("sourceUrl") if isinstance(d, dict) else None
            if url:
                RssSourceDao.delete(url)
        return rd.set_data("已执行")


# ---------------------------------------------------------------------------
# ReplaceRuleController
# ---------------------------------------------------------------------------

class ReplaceRuleController:
    @staticmethod
    def all_rules() -> ReturnData:
        rd = ReturnData()
        rules = ReplaceRuleDao.all()
        return rd.set_data(rules)

    @staticmethod
    def save_rule(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        d = _parse_json(post_data)
        if d is None:
            return rd.set_error_msg("数据不能为空")
        rule = _replace_from_dict(d)
        if rule.order == -2147483648:
            rule.order = ReplaceRuleDao.max_order() + 1
        if not rule.id:
            rule.id = int(time.time() * 1000)
        ReplaceRuleDao.insert(rule)
        return rd.set_data(rule)

    @staticmethod
    def delete(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        d = _parse_json(post_data)
        if d is None:
            return rd.set_error_msg("数据不能为空")
        rule = _replace_from_dict(d)
        ReplaceRuleDao.delete(rule)
        return rd.set_data("")

    @staticmethod
    def test_rule(post_data: Optional[str]) -> ReturnData:
        rd = ReturnData()
        d = _parse_json(post_data)
        if not isinstance(d, dict):
            return rd.set_error_msg("数据不能为空")
        rule_d = d.get("rule")
        text = d.get("text", "")
        if not rule_d:
            return rd.set_error_msg("缺少rule")
        rule = _replace_from_dict(rule_d) if isinstance(rule_d, dict) else None
        if not rule:
            return rd.set_error_msg("格式不对")
        try:
            if rule.isRegex:
                result = re.sub(rule.pattern, rule.replacement, text)
            else:
                result = text.replace(rule.pattern, rule.replacement)
        except re.error as e:
            return rd.set_error_msg(f"正则错误: {e}")
        return rd.set_data(result)
