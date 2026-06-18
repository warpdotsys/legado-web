"""SQLite persistence layer mirroring legado's Room database.

Schema matches app/src/main/java/io/legado/app/data/entities so the web
service stores books / sources / rules exactly the way the Android app does.
"""

import sqlite3
import threading
import time
import json
import os
from typing import Optional, List
from dataclasses import asdict, fields, is_dataclass

from models import (
    Book, BookChapter, BookSource, RssSource, ReplaceRule,
)


DB_PATH = os.environ.get("LEGADO_DB", "/data/legado.db")

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Each thread gets its own connection; sqlite3 is thread-local safe."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    bookUrl TEXT PRIMARY KEY,
    tocUrl TEXT DEFAULT '',
    origin TEXT DEFAULT 'loc_book',
    originName TEXT DEFAULT '',
    name TEXT DEFAULT '',
    author TEXT DEFAULT '',
    kind TEXT,
    customTag TEXT,
    coverUrl TEXT,
    customCoverUrl TEXT,
    intro TEXT,
    customIntro TEXT,
    charset TEXT,
    type INTEGER DEFAULT 0,
    "group" INTEGER DEFAULT 0,
    latestChapterTitle TEXT,
    latestChapterTime INTEGER DEFAULT 0,
    lastCheckTime INTEGER DEFAULT 0,
    lastCheckCount INTEGER DEFAULT 0,
    totalChapterNum INTEGER DEFAULT 0,
    durChapterTitle TEXT,
    durChapterIndex INTEGER DEFAULT 0,
    durChapterPos INTEGER DEFAULT 0,
    durChapterTime INTEGER DEFAULT 0,
    wordCount TEXT DEFAULT '',
    canUpdate INTEGER DEFAULT 1,
    "order" INTEGER DEFAULT 0,
    originOrder INTEGER DEFAULT 0,
    variable TEXT,
    readConfig TEXT
);

CREATE TABLE IF NOT EXISTS chapters (
    url TEXT NOT NULL,
    bookUrl TEXT NOT NULL,
    title TEXT DEFAULT '',
    isVolume INTEGER DEFAULT 0,
    baseUrl TEXT DEFAULT '',
    "index" INTEGER DEFAULT 0,
    isVip INTEGER DEFAULT 0,
    isPay INTEGER DEFAULT 0,
    resourceUrl TEXT,
    tag TEXT,
    wordCount TEXT,
    start INTEGER,
    end INTEGER,
    startFragmentId TEXT,
    endFragmentId TEXT,
    variable TEXT,
    imgUrl TEXT,
    PRIMARY KEY (url, bookUrl),
    FOREIGN KEY (bookUrl) REFERENCES books(bookUrl) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS book_sources (
    bookSourceUrl TEXT PRIMARY KEY,
    bookSourceName TEXT DEFAULT '',
    bookSourceGroup TEXT,
    bookSourceType INTEGER DEFAULT 0,
    bookUrlPattern TEXT,
    customOrder INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    enabledExplore INTEGER DEFAULT 1,
    jsLib TEXT,
    enabledCookieJar INTEGER DEFAULT 1,
    concurrentRate TEXT,
    header TEXT,
    loginUrl TEXT,
    loginUi TEXT,
    loginCheckJs TEXT,
    coverDecodeJs TEXT,
    bookSourceComment TEXT,
    variableComment TEXT,
    lastUpdateTime INTEGER DEFAULT 0,
    respondTime INTEGER DEFAULT 180000,
    weight INTEGER DEFAULT 0,
    exploreUrl TEXT,
    exploreScreen TEXT,
    ruleExplore TEXT,
    searchUrl TEXT,
    ruleSearch TEXT,
    ruleBookInfo TEXT,
    ruleToc TEXT,
    ruleContent TEXT,
    ruleReview TEXT,
    eventListener INTEGER DEFAULT 0,
    customButton INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rss_sources (
    sourceUrl TEXT PRIMARY KEY,
    sourceName TEXT DEFAULT '',
    sourceIcon TEXT DEFAULT '',
    sourceGroup TEXT,
    sourceComment TEXT,
    enabled INTEGER DEFAULT 1,
    variableComment TEXT,
    jsLib TEXT,
    enabledCookieJar INTEGER DEFAULT 1,
    concurrentRate TEXT,
    header TEXT,
    loginUrl TEXT,
    loginUi TEXT,
    loginCheckJs TEXT,
    coverDecodeJs TEXT,
    sortUrl TEXT,
    singleUrl INTEGER DEFAULT 0,
    articleStyle INTEGER DEFAULT 0,
    ruleArticles TEXT,
    ruleNextPage TEXT,
    ruleTitle TEXT,
    rulePubDate TEXT,
    ruleDescription TEXT,
    ruleImage TEXT,
    ruleLink TEXT,
    ruleContent TEXT,
    customOrder INTEGER DEFAULT 0,
    lastUpdateTime INTEGER DEFAULT 0,
    respondTime INTEGER DEFAULT 180000,
    weight INTEGER DEFAULT 0,
    variable TEXT
);

CREATE TABLE IF NOT EXISTS replace_rules (
    id INTEGER PRIMARY KEY,
    name TEXT DEFAULT '',
    "group" TEXT,
    pattern TEXT DEFAULT '',
    replacement TEXT DEFAULT '',
    scope TEXT,
    scopeTitle INTEGER DEFAULT 0,
    scopeContent INTEGER DEFAULT 1,
    excludeScope TEXT,
    isEnabled INTEGER DEFAULT 1,
    isRegex INTEGER DEFAULT 0,
    "order" INTEGER DEFAULT -2147483648,
    timeoutMillisecond INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS read_config (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

# Columns where the model field is a nested dataclass / dict stored as JSON.
JSON_COLUMNS_SOURCE = {
    "ruleExplore", "ruleSearch", "ruleBookInfo", "ruleToc",
    "ruleContent", "ruleReview",
}
BOOL_COLUMNS_SOURCE = {
    "enabled", "enabledExplore", "eventListener", "customButton",
    "enabledCookieJar",
}
BOOL_COLUMNS_RSS = {
    "enabled", "enabledCookieJar", "singleUrl",
}
BOOL_COLUMNS_BOOK = {"canUpdate"}
BOOL_COLUMNS_CHAPTER = {"isVolume", "isVip", "isPay"}
BOOL_COLUMNS_REPLACE = {
    "scopeTitle", "scopeContent", "isEnabled", "isRegex",
}


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return bool(int(v))


def _book_from_row(row) -> Book:
    return Book(
        bookUrl=row["bookUrl"], tocUrl=row["tocUrl"], origin=row["origin"],
        originName=row["originName"], name=row["name"], author=row["author"],
        kind=row["kind"], customTag=row["customTag"], coverUrl=row["coverUrl"],
        customCoverUrl=row["customCoverUrl"], intro=row["intro"],
        customIntro=row["customIntro"], charset=row["charset"],
        type=row["type"], group=row["group"],
        latestChapterTitle=row["latestChapterTitle"],
        latestChapterTime=row["latestChapterTime"],
        lastCheckTime=row["lastCheckTime"],
        lastCheckCount=row["lastCheckCount"],
        totalChapterNum=row["totalChapterNum"],
        durChapterTitle=row["durChapterTitle"],
        durChapterIndex=row["durChapterIndex"],
        durChapterPos=row["durChapterPos"],
        durChapterTime=row["durChapterTime"],
        wordCount=row["wordCount"],
        canUpdate=_to_bool(row["canUpdate"]),
        order=row["order"], originOrder=row["originOrder"],
        variable=row["variable"], readConfig=row["readConfig"],
    )


def _chapter_from_row(row) -> BookChapter:
    return BookChapter(
        url=row["url"], title=row["title"],
        isVolume=_to_bool(row["isVolume"]), baseUrl=row["baseUrl"],
        bookUrl=row["bookUrl"], index=row["index"],
        isVip=_to_bool(row["isVip"]), isPay=_to_bool(row["isPay"]),
        resourceUrl=row["resourceUrl"], tag=row["tag"],
        wordCount=row["wordCount"], start=row["start"], end=row["end"],
        startFragmentId=row["startFragmentId"],
        endFragmentId=row["endFragmentId"],
        variable=row["variable"], imgUrl=row["imgUrl"],
    )


class BookDao:
    @staticmethod
    def all() -> List[Book]:
        conn = get_conn()
        rows = conn.execute(
            'SELECT * FROM books ORDER BY "order", durChapterTime DESC'
        ).fetchall()
        return [_book_from_row(r) for r in rows]

    @staticmethod
    def get_book(book_url: str) -> Optional[Book]:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM books WHERE bookUrl=?", (book_url,)
        ).fetchone()
        return _book_from_row(row) if row else None

    @staticmethod
    def get_book_by_name(name: str, author: str) -> Optional[Book]:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM books WHERE name=? AND author=?", (name, author)
        ).fetchone()
        return _book_from_row(row) if row else None

    @staticmethod
    def insert(book: Book) -> None:
        conn = get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO books
            (bookUrl,tocUrl,origin,originName,name,author,kind,customTag,
             coverUrl,customCoverUrl,intro,customIntro,charset,type,"group",
             latestChapterTitle,latestChapterTime,lastCheckTime,lastCheckCount,
             totalChapterNum,durChapterTitle,durChapterIndex,durChapterPos,
             durChapterTime,wordCount,canUpdate,"order",originOrder,
             variable,readConfig)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (book.bookUrl, book.tocUrl, book.origin, book.originName,
             book.name, book.author, book.kind, book.customTag,
             book.coverUrl, book.customCoverUrl, book.intro, book.customIntro,
             book.charset, book.type, book.group,
             book.latestChapterTitle, book.latestChapterTime,
             book.lastCheckTime, book.lastCheckCount, book.totalChapterNum,
             book.durChapterTitle, book.durChapterIndex, book.durChapterPos,
             book.durChapterTime, book.wordCount,
             1 if book.canUpdate else 0, book.order, book.originOrder,
             book.variable, book.readConfig),
        )
        conn.commit()

    @staticmethod
    def update(book: Book) -> None:
        BookDao.insert(book)

    @staticmethod
    def delete(book: Book) -> None:
        conn = get_conn()
        conn.execute("DELETE FROM books WHERE bookUrl=?", (book.bookUrl,))
        conn.commit()


class BookChapterDao:
    @staticmethod
    def get_chapter_list(book_url: str) -> List[BookChapter]:
        conn = get_conn()
        rows = conn.execute(
            'SELECT * FROM chapters WHERE bookUrl=? ORDER BY "index"',
            (book_url,),
        ).fetchall()
        return [_chapter_from_row(r) for r in rows]

    @staticmethod
    def get_chapter(book_url: str, index: int) -> Optional[BookChapter]:
        conn = get_conn()
        row = conn.execute(
            'SELECT * FROM chapters WHERE bookUrl=? AND "index"=?',
            (book_url, index),
        ).fetchone()
        return _chapter_from_row(row) if row else None

    @staticmethod
    def replace_all(book_url: str, chapters: List[BookChapter]) -> None:
        conn = get_conn()
        conn.execute("DELETE FROM chapters WHERE bookUrl=?", (book_url,))
        conn.executemany(
            """INSERT OR REPLACE INTO chapters
            (url,bookUrl,title,isVolume,baseUrl,"index",isVip,isPay,
             resourceUrl,tag,wordCount,start,end,startFragmentId,
             endFragmentId,variable,imgUrl)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(c.url, c.bookUrl, c.title, 1 if c.isVolume else 0, c.baseUrl,
              c.index, 1 if c.isVip else 0, 1 if c.isPay else 0,
              c.resourceUrl, c.tag, c.wordCount, c.start, c.end,
              c.startFragmentId, c.endFragmentId, c.variable, c.imgUrl)
             for c in chapters],
        )
        conn.commit()

    @staticmethod
    def del_by_book(book_url: str) -> None:
        conn = get_conn()
        conn.execute("DELETE FROM chapters WHERE bookUrl=?", (book_url,))
        conn.commit()


def _source_from_row(row, cls):
    """Build a BookSource/RssSource from a row, decoding JSON rule fields."""
    data = {}
    for f in fields(cls):
        col = f.name
        val = row[col] if col in row.keys() else None
        if col in JSON_COLUMNS_SOURCE and val:
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                val = None
        elif col in BOOL_COLUMNS_SOURCE and cls is BookSource:
            val = _to_bool(val)
        elif col in BOOL_COLUMNS_RSS and cls is RssSource:
            val = _to_bool(val)
        data[col] = val
    return cls(**{k: v for k, v in data.items()})


class BookSourceDao:
    @staticmethod
    def all() -> List[BookSource]:
        conn = get_conn()
        rows = conn.execute(
            'SELECT * FROM book_sources ORDER BY customOrder, bookSourceName'
        ).fetchall()
        return [_source_from_row(r, BookSource) for r in rows]

    @staticmethod
    def get_book_source(url: str) -> Optional[BookSource]:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM book_sources WHERE bookSourceUrl=?", (url,)
        ).fetchone()
        return _source_from_row(row, BookSource) if row else None

    @staticmethod
    def insert(source: BookSource) -> None:
        BookSourceDao._upsert(source)

    @staticmethod
    def _upsert(source: BookSource) -> None:
        conn = get_conn()
        d = asdict(source)
        for col in JSON_COLUMNS_SOURCE:
            d[col] = json.dumps(d[col], ensure_ascii=False) if d[col] else None
        for col in BOOL_COLUMNS_SOURCE:
            d[col] = 1 if d[col] else 0
        conn.execute(
            """INSERT OR REPLACE INTO book_sources
            (bookSourceUrl,bookSourceName,bookSourceGroup,bookSourceType,
             bookUrlPattern,customOrder,enabled,enabledExplore,jsLib,
             enabledCookieJar,concurrentRate,header,loginUrl,loginUi,
             loginCheckJs,coverDecodeJs,bookSourceComment,variableComment,
             lastUpdateTime,respondTime,weight,exploreUrl,exploreScreen,
             ruleExplore,searchUrl,ruleSearch,ruleBookInfo,ruleToc,
             ruleContent,ruleReview,eventListener,customButton)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["bookSourceUrl"], d["bookSourceName"], d["bookSourceGroup"],
             d["bookSourceType"], d["bookUrlPattern"], d["customOrder"],
             d["enabled"], d["enabledExplore"], d["jsLib"],
             d["enabledCookieJar"], d["concurrentRate"], d["header"],
             d["loginUrl"], d["loginUi"], d["loginCheckJs"],
             d["coverDecodeJs"], d["bookSourceComment"],
             d["variableComment"], d["lastUpdateTime"], d["respondTime"],
             d["weight"], d["exploreUrl"], d["exploreScreen"],
             d["ruleExplore"], d["searchUrl"], d["ruleSearch"],
             d["ruleBookInfo"], d["ruleToc"], d["ruleContent"],
             d["ruleReview"], d["eventListener"], d["customButton"]),
        )
        conn.commit()

    @staticmethod
    def delete(url: str) -> None:
        conn = get_conn()
        conn.execute(
            "DELETE FROM book_sources WHERE bookSourceUrl=?", (url,)
        )
        conn.commit()


class RssSourceDao:
    @staticmethod
    def all() -> List[RssSource]:
        conn = get_conn()
        rows = conn.execute(
            'SELECT * FROM rss_sources ORDER BY customOrder, sourceName'
        ).fetchall()
        return [_source_from_row(r, RssSource) for r in rows]

    @staticmethod
    def get_source(url: str) -> Optional[RssSource]:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM rss_sources WHERE sourceUrl=?", (url,)
        ).fetchone()
        return _source_from_row(row, RssSource) if row else None

    @staticmethod
    def insert(source: RssSource) -> None:
        conn = get_conn()
        d = asdict(source)
        for col in BOOL_COLUMNS_RSS:
            d[col] = 1 if d[col] else 0
        conn.execute(
            """INSERT OR REPLACE INTO rss_sources
            (sourceUrl,sourceName,sourceIcon,sourceGroup,sourceComment,
             enabled,variableComment,jsLib,enabledCookieJar,concurrentRate,
             header,loginUrl,loginUi,loginCheckJs,coverDecodeJs,sortUrl,
             singleUrl,articleStyle,ruleArticles,ruleNextPage,ruleTitle,
             rulePubDate,ruleDescription,ruleImage,ruleLink,ruleContent,
             customOrder,lastUpdateTime,respondTime,weight,variable)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["sourceUrl"], d["sourceName"], d["sourceIcon"],
             d["sourceGroup"], d["sourceComment"], d["enabled"],
             d["variableComment"], d["jsLib"], d["enabledCookieJar"],
             d["concurrentRate"], d["header"], d["loginUrl"], d["loginUi"],
             d["loginCheckJs"], d["coverDecodeJs"], d["sortUrl"],
             d["singleUrl"], d["articleStyle"], d["ruleArticles"],
             d["ruleNextPage"], d["ruleTitle"], d["rulePubDate"],
             d["ruleDescription"], d["ruleImage"], d["ruleLink"],
             d["ruleContent"], d["customOrder"], d["lastUpdateTime"],
             d["respondTime"], d["weight"], d["variable"]),
        )
        conn.commit()

    @staticmethod
    def delete(url: str) -> None:
        conn = get_conn()
        conn.execute("DELETE FROM rss_sources WHERE sourceUrl=?", (url,))
        conn.commit()


def _replace_from_row(row) -> ReplaceRule:
    return ReplaceRule(
        id=row["id"], name=row["name"], group=row["group"],
        pattern=row["pattern"], replacement=row["replacement"],
        scope=row["scope"],
        scopeTitle=_to_bool(row["scopeTitle"]),
        scopeContent=_to_bool(row["scopeContent"]),
        excludeScope=row["excludeScope"],
        isEnabled=_to_bool(row["isEnabled"]),
        isRegex=_to_bool(row["isRegex"]),
        order=row["order"], timeoutMillisecond=row["timeoutMillisecond"],
    )


class ReplaceRuleDao:
    @staticmethod
    def all() -> List[ReplaceRule]:
        conn = get_conn()
        rows = conn.execute(
            'SELECT * FROM replace_rules ORDER BY "order"'
        ).fetchall()
        return [_replace_from_row(r) for r in rows]

    @staticmethod
    def max_order() -> int:
        conn = get_conn()
        row = conn.execute(
            'SELECT COALESCE(MAX("order"), -1) AS m FROM replace_rules'
        ).fetchone()
        return int(row["m"])

    @staticmethod
    def insert(rule: ReplaceRule) -> None:
        conn = get_conn()
        d = asdict(rule)
        for col in BOOL_COLUMNS_REPLACE:
            d[col] = 1 if d[col] else 0
        conn.execute(
            """INSERT OR REPLACE INTO replace_rules
            (id,name,"group",pattern,replacement,scope,scopeTitle,
             scopeContent,excludeScope,isEnabled,isRegex,"order",
             timeoutMillisecond)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["id"], d["name"], d["group"], d["pattern"],
             d["replacement"], d["scope"], d["scopeTitle"],
             d["scopeContent"], d["excludeScope"], d["isEnabled"],
             d["isRegex"], d["order"], d["timeoutMillisecond"]),
        )
        conn.commit()

    @staticmethod
    def delete(rule: ReplaceRule) -> None:
        conn = get_conn()
        conn.execute("DELETE FROM replace_rules WHERE id=?", (rule.id,))
        conn.commit()


class ReadConfigDao:
    @staticmethod
    def get() -> str:
        conn = get_conn()
        row = conn.execute(
            "SELECT value FROM read_config WHERE key='web'"
        ).fetchone()
        return row["value"] if row else "{}"

    @staticmethod
    def save(value: str) -> None:
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO read_config (key, value) VALUES ('web', ?)",
            (value,),
        )
        conn.commit()


def seed_demo_data() -> None:
    """Seed an example book source so a fresh container is usable."""
    init_db()
    if BookSourceDao.all():
        return
    demo = BookSource(
        bookSourceUrl="https://www.bqg70.com",
        bookSourceName="笔趣阁(示例源)",
        bookSourceGroup="示例",
        enabled=True,
        searchUrl="https://www.bqg70.com/search?q={{key}}",
    )
    BookSourceDao.insert(demo)
