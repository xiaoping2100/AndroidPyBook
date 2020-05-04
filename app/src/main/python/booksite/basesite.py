# coding=utf-8

from dataclasses import dataclass
from typing import List, Any, Optional
import requests


@dataclass
class SiteInfo:
    type: str  # 网络小说; 文学；英文
    statue: str  # 稳定版本；上线版本
    name: str
    brief_name: str
    url: str
    max_threading_number: int = 50  # 并行访问的最大线程数量


class BaseSite:
    """
    具体查询小说网站的父类，每个子类需要提供三个方法\n
    get_books 根据search_info（用户名或密码）查询小说列表\n
    get_chapters 根据book（含书籍的url地址）查询某本小说的章节信息\n
    get_chapter_content 根据chapter（含章节的url地址）查询某章节的内容\n
    """

    @classmethod
    def try_get_url(cls, session: requests.session, url: str, *,
                    try_times: int = 3, try_timeout: int = 10, **kwargs) -> Optional[requests.Response]:
        for _ in range(try_times):
            try:
                r = session.get(url=url, timeout=try_timeout, **kwargs)
                return r
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
                pass
        return None

    @classmethod
    def try_post_url(cls, session: requests.session, url: str, *,
                     try_times: int = 3, try_timeout: int = 10, **kwargs) -> Optional[requests.Response]:
        for _ in range(try_times):
            try:
                r = session.post(url=url, timeout=try_timeout, **kwargs)
                return r
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
                pass
        return None

    def __init__(self, site_info: SiteInfo):
        self.site_info = site_info

    def get_books(self, search_info: str) -> List[Any]:
        """
        根据search_info搜索书籍的简介，作者信息等，搜索结果的最大数量为self.get_books_max_number\n
        参数：
            search_info: 书名 或 作者名
        返回值：
            列表， 格式为[book1,book2,... ]
            book格式见Book类型
        使用方法：
            用户通过get_books获取返回值后，可以根据book_brief信息选择具体的book下载
        """
        raise NotImplementedError

    def get_chapters(self, book) -> List[Any]:
        """
        根据book中的url信息, 获取书籍的章节信息\n
        输入：
            book： Book类型
        返回值：
            列表， 格式为[chapter1,chapter2,... ]\n
            chapter格式见Chapter类型
        """
        raise NotImplementedError

    def get_chapter_content(self, chapter) -> str:
        """
        根据chapter中的url信息, 获取章节的具体内容\n
        参数：
            chapter： Chapter类型\n
        返回值：
            content: 章节的具体内容
        """
        raise NotImplementedError

    def save_chapter(self, chapter, filename: str) -> None:
        """
        根据chapter中的url信息, 获取章节的具体内容,保存到文件中\n
        参数：
            chapter： Chapter类型\n
            filename： 文件名，str类型\n
        返回值：
        """
        raise NotImplementedError


@dataclass
class Book:
    site: BaseSite
    url: str
    name: str
    author: str
    brief: str


@dataclass
class Chapter:
    site: BaseSite
    url: str
    title: str
