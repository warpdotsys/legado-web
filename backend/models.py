"""Data entities mirroring legado app/src/main/java/io/legado/app/data/entities.

These map 1:1 with the Android Room entities so JSON exchanged over the
port-1122 web API stays wire-compatible with the original legado clients.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Any


def _asdict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_asdict(x) for x in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _asdict(v) for k, v in asdict(obj).items()}
    return obj


@dataclass
class Book:
    bookUrl: str = ""
    tocUrl: str = ""
    origin: str = "loc_book"
    originName: str = ""
    name: str = ""
    author: str = ""
    kind: Optional[str] = None
    customTag: Optional[str] = None
    coverUrl: Optional[str] = None
    customCoverUrl: Optional[str] = None
    intro: Optional[str] = None
    customIntro: Optional[str] = None
    charset: Optional[str] = None
    type: int = 0
    group: int = 0
    latestChapterTitle: Optional[str] = None
    latestChapterTime: int = 0
    lastCheckTime: int = 0
    lastCheckCount: int = 0
    totalChapterNum: int = 0
    durChapterTitle: Optional[str] = None
    durChapterIndex: int = 0
    durChapterPos: int = 0
    durChapterTime: int = 0
    wordCount: str = ""
    canUpdate: bool = True
    order: int = 0
    originOrder: int = 0
    variable: Optional[str] = None
    readConfig: Optional[str] = None


@dataclass
class BookChapter:
    url: str = ""
    title: str = ""
    isVolume: bool = False
    baseUrl: str = ""
    bookUrl: str = ""
    index: int = 0
    isVip: bool = False
    isPay: bool = False
    resourceUrl: Optional[str] = None
    tag: Optional[str] = None
    wordCount: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    startFragmentId: Optional[str] = None
    endFragmentId: Optional[str] = None
    variable: Optional[str] = None
    imgUrl: Optional[str] = None


@dataclass
class BookProgress:
    name: str = ""
    author: str = ""
    durChapterIndex: int = 0
    durChapterPos: int = 0
    durChapterTime: int = 0
    durChapterTitle: Optional[str] = None


@dataclass
class SearchRule:
    bookList: Optional[str] = None
    name: Optional[str] = None
    author: Optional[str] = None
    intro: Optional[str] = None
    kind: Optional[str] = None
    lastChapter: Optional[str] = None
    updateTime: Optional[str] = None
    bookUrl: Optional[str] = None
    coverUrl: Optional[str] = None
    wordCount: Optional[str] = None


@dataclass
class ExploreRule:
    bookList: Optional[str] = None
    name: Optional[str] = None
    author: Optional[str] = None
    intro: Optional[str] = None
    kind: Optional[str] = None
    lastChapter: Optional[str] = None
    updateTime: Optional[str] = None
    bookUrl: Optional[str] = None
    coverUrl: Optional[str] = None
    wordCount: Optional[str] = None


@dataclass
class BookInfoRule:
    init: Optional[str] = None
    name: Optional[str] = None
    author: Optional[str] = None
    intro: Optional[str] = None
    kind: Optional[str] = None
    lastChapter: Optional[str] = None
    updateTime: Optional[str] = None
    coverUrl: Optional[str] = None
    tocUrl: Optional[str] = None
    wordCount: Optional[str] = None


@dataclass
class TocRule:
    chapterList: Optional[str] = None
    chapterName: Optional[str] = None
    chapterUrl: Optional[str] = None
    isVolume: Optional[str] = None
    isVip: Optional[str] = None
    isPay: Optional[str] = None
    updateTime: Optional[str] = None
    nextTocUrl: Optional[str] = None


@dataclass
class ContentRule:
    content: Optional[str] = None
    title: Optional[str] = None
    nextContentUrl: Optional[str] = None
    webJs: Optional[str] = None
    sourceRegex: Optional[str] = None
    replaceRegex: Optional[str] = None
    imageStyle: Optional[str] = None
    imageDecodeJs: Optional[str] = None
    payAction: Optional[str] = None


@dataclass
class ReviewRule:
    reviewUrl: Optional[str] = None
    reviewList: Optional[str] = None
    content: Optional[str] = None
    avatar: Optional[str] = None
    userName: Optional[str] = None
    postTime: Optional[str] = None
    voteUps: Optional[str] = None


@dataclass
class BookSource:
    bookSourceUrl: str = ""
    bookSourceName: str = ""
    bookSourceGroup: Optional[str] = None
    bookSourceType: int = 0
    bookUrlPattern: Optional[str] = None
    customOrder: int = 0
    enabled: bool = True
    enabledExplore: bool = True
    jsLib: Optional[str] = None
    enabledCookieJar: Optional[bool] = True
    concurrentRate: Optional[str] = None
    header: Optional[str] = None
    loginUrl: Optional[str] = None
    loginUi: Optional[str] = None
    loginCheckJs: Optional[str] = None
    coverDecodeJs: Optional[str] = None
    bookSourceComment: Optional[str] = None
    variableComment: Optional[str] = None
    lastUpdateTime: int = 0
    respondTime: int = 180000
    weight: int = 0
    exploreUrl: Optional[str] = None
    exploreScreen: Optional[str] = None
    ruleExplore: Optional[ExploreRule] = None
    searchUrl: Optional[str] = None
    ruleSearch: Optional[SearchRule] = None
    ruleBookInfo: Optional[BookInfoRule] = None
    ruleToc: Optional[TocRule] = None
    ruleContent: Optional[ContentRule] = None
    ruleReview: Optional[ReviewRule] = None
    eventListener: bool = False
    customButton: bool = False


@dataclass
class RssSource:
    sourceUrl: str = ""
    sourceName: str = ""
    sourceIcon: str = ""
    sourceGroup: Optional[str] = None
    sourceComment: Optional[str] = None
    enabled: bool = True
    variableComment: Optional[str] = None
    jsLib: Optional[str] = None
    enabledCookieJar: Optional[bool] = True
    concurrentRate: Optional[str] = None
    header: Optional[str] = None
    loginUrl: Optional[str] = None
    loginUi: Optional[str] = None
    loginCheckJs: Optional[str] = None
    coverDecodeJs: Optional[str] = None
    sortUrl: Optional[str] = None
    singleUrl: bool = False
    articleStyle: int = 0
    ruleArticles: Optional[str] = None
    ruleNextPage: Optional[str] = None
    ruleTitle: Optional[str] = None
    rulePubDate: Optional[str] = None
    ruleDescription: Optional[str] = None
    ruleImage: Optional[str] = None
    ruleLink: Optional[str] = None
    ruleContent: Optional[str] = None
    customOrder: int = 0
    lastUpdateTime: int = 0
    respondTime: int = 180000
    weight: int = 0
    variable: Optional[str] = None


@dataclass
class ReplaceRule:
    id: int = 0
    name: str = ""
    group: Optional[str] = None
    pattern: str = ""
    replacement: str = ""
    scope: Optional[str] = None
    scopeTitle: bool = False
    scopeContent: bool = True
    excludeScope: Optional[str] = None
    isEnabled: bool = True
    isRegex: bool = False
    order: int = -2147483648
    timeoutMillisecond: int = 0
