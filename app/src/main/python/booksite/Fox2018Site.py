import copy
import re

import chardet
import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import List

from .basesite import SiteInfo,BaseSite, Book, Chapter


class Fox2018Site(BaseSite):
    def __init__(self):
        self.site_info = SiteInfo(
            type='文学',
            statue='上线版本',
            url='http://www.fox2018.com',
            name='青少年读书网',
            brief_name='青少年',
            max_threading_number=50,
        )
        super().__init__(self.site_info)
        self.base_url = 'http://www.fox2018.com'
        self.encoding = 'GB2312'
        self.search_url = 'http://www.fox2018.com/e/search/index.php'
        self.session = requests.session()

    def get_books(self, search_info: str) -> List[Book]:
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                   'Content-Type': 'application/x-www-form-urlencoded',
                   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:75.0) Gecko/20100101 Firefox/75.0'}
        # data = {'keyboard': urllib.parse.quote(search_info.encode(self.encoding))，..} # 不能用字典形式，耗费5月2日半天时间
        data = f'show=title&classid=1&tempid=4&keyboard={urllib.parse.quote(search_info.encode(self.encoding))}'
        r = self.try_post_url(self.session, url=self.search_url, try_timeout=5,
                              headers=headers, data=data)
        if r is None:
            return []
        soup = BeautifulSoup(r.content.decode(self.encoding, 'ignore'), 'html.parser')
        # soup = BeautifulSoup(r.content, 'html.parser')
        if not (book_soup_list := soup.select('div.classify_list a')):
            return []

        search_book_results = []
        for book_soup in book_soup_list:
            book_url = self.base_url + book_soup.attrs['href']
            book_name = book_soup.select_one('h3').text
            book_author = book_soup.select_one('p.author i').text
            book_brief = book_soup.select_one('p.brief').text
            book = Book(site=self, url=book_url, name=book_name, author=book_author,
                        brief=book_brief)
            search_book_results.append(book)
        return search_book_results

    def get_chapters(self, book: Book) -> List[Chapter]:
        r = self.try_get_url(self.session, book.url)
        if r is None:
            return []

        soup = BeautifulSoup(r.content.decode(self.encoding, 'ignore'), 'html.parser')
        chapter_soup_list = soup.select('div.book_directory_lost li a')
        chapters = [Chapter(site=self,
                            url=self.base_url + chapter.attrs['href'],
                            title=chapter.text)
                    for chapter in chapter_soup_list]
        return chapters

    def get_chapter_content(self, chapter: Chapter) -> str:
        session = copy.deepcopy(self.session)
        r = self.try_get_url(session, chapter.url)
        session.close()
        if r is None:
            return f'{chapter.title}\r\n下载失败'

        soup = BeautifulSoup(r.content.decode(self.encoding, 'ignore'), 'html.parser')
        content = soup.select_one('div.content_tet').text.strip()
        # title = chapter.title if chapter.title.startswith("第") else f"第{chapter.title}"
        # content2 = f'\r\n{title}\r\n{content}'
        return content

    def save_chapter(self, chapter, filename):
        content = self.get_chapter_content(chapter)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
