import copy
import itertools
import re

import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import List

# 采用下面的方法，同时支持正常import和动态加载
try:
    import basesite
except (ModuleNotFoundError, ImportError) as e:
    from . import basesite


class CuohengSite(basesite.BaseSite):
    def __init__(self):
        self.site_info = basesite.SiteInfo(
            type='文学',
            statue='上线版本',
            url='http://cuoheng.com',
            name='错衡文学网',
            brief_name='错衡网',
            version='1.1',
            max_threading_number=50,
        )
        super().__init__(self.site_info)
        self.base_url = 'http://cuoheng.com/'
        self.encoding = 'utf-8'
        self.search_url = 'http://cuoheng.com/?s=%s'
        self.session = requests.session()

    @basesite.print_in_out
    def get_books(self, search_info: str) -> List[basesite.Book]:
        url = self.search_url % urllib.parse.quote(search_info)
        r = self.try_get_url(self.session, url, try_timeout=5)
        if r is None or r.text.find("没有找到有关") >= 0:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        book_soup_list = soup.select('div.content > article')
        search_book_results = []
        for book_soup in book_soup_list:
            tmp_soup = book_soup.select_one('header > h2 > a')
            book_url = tmp_soup.attrs['href']
            m = re.search(r'《(.*?)》.* (\w+) 著', tmp_soup.text)
            book_name = m.group(1)
            book_author = m.group(2)
            tmp_text = book_soup.select_one('p.note').text
            if m2 := re.search(r"简介(：)?(.*)", tmp_text):
                book_brief = m2.group(2).strip()
            else:
                book_brief = tmp_text.strip()
            book = basesite.Book(site=self, url=book_url, name=book_name, author=book_author,
                                 brief=book_brief)
            search_book_results.append(book)
        return search_book_results

    @basesite.print_in_out
    def get_chapters(self, book: basesite.Book) -> List[basesite.Chapter]:
        book_base_url = book.url.replace('info.html', '')
        r = self.try_get_url(self.session, book_base_url + 'index.html')
        if r is None:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        chapter_soup_lists = soup.select('div.content div.Volume')[1:]
        chapter_soup_list = itertools.chain(*(i.select('dd > a') for i in chapter_soup_lists))
        chapters = [basesite.Chapter(site=self,
                                     url=book_base_url + chapter.attrs['href'],
                                     title=chapter.text)
                    for chapter in chapter_soup_list]
        return chapters

    def get_chapter_content(self, chapter: basesite.Chapter) -> str:
        session = copy.deepcopy(self.session)
        r = self.try_get_url(session, chapter.url)
        session.close()
        if r is None:
            return f'\r\n{chapter.title}\r\n下载失败'

        soup = BeautifulSoup(r.content, 'html.parser')
        content = soup.select_one('div.content').text.strip()
        # content2 = f'\r\n{chapter.title}\r\n{content}'
        return content

    def save_chapter(self, chapter, filename):
        content = self.get_chapter_content(chapter)
        with open(filename, 'w', encoding=self.encoding) as f:
            f.write(content)
