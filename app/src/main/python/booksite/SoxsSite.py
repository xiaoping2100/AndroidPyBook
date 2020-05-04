import copy
import re

import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import List

from .basesite import SiteInfo,BaseSite, Book, Chapter


class SoxsSite(BaseSite):
    def __init__(self):
        self.site_info = SiteInfo(
            type='网络小说',
            statue='上线版本',
            url='https://www.soxs.cc',
            name='搜小说',
            brief_name='搜小说',
            max_threading_number=50,
        )
        super().__init__(self.site_info)
        self.base_url = 'https://www.soxs.cc'
        self.encoding = 'utf-8'
        self.search_url = 'https://www.soxs.cc/search.html'
        self.session = requests.session()

    def get_books(self, search_info: str) -> List[Book]:
        r = self.try_post_url(self.session, url=self.search_url, try_timeout=5,
                              params=f'searchtype=all&searchkey={urllib.parse.quote(search_info)}')
        if r is None:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        book_tag_list = soup.select('div.novelslist2 > ul > li')
        book_num = len(book_tag_list) - 1
        if book_num == 0:
            return []

        search_book_results = []
        book_soup_list = book_tag_list[1:]
        for book_soup in book_soup_list:
            span_list = book_soup.findAll('span')
            book_url = self.base_url + span_list[1].find('a').attrs['href']
            book_name = span_list[1].find('a').text
            book_author = span_list[3].text
            book_brief = f"最新章节:{span_list[2].find('a').text} 更新时间:{span_list[4].text.strip()}"
            book = Book(site=self, url=book_url, name=book_name, author=book_author,
                        brief=book_brief)
            search_book_results.append(book)
        return search_book_results

    def get_chapters(self, book: Book) -> List[Chapter]:
        r = self.try_get_url(self.session, book.url)
        if r is None:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        chapter_soup_list = soup.select('div.caption + div  dd a')
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

        soup = BeautifulSoup(r.content, 'html.parser')
        content = soup.select_one('div.content').text
        content2 = re.sub(r"您可以在百度.+查找最新章节！", "", content)
        if m := re.search(r"\w+最新章节地址：https://www.soxs.cc", content2):
            content2 = content2[:m.start()].strip()

        # title = chapter.title if chapter.title.startswith("第") else f"第{chapter.title}"
        # content3 = f'\r\n{title}\r\n{content2.strip()}'
        return content2

    def save_chapter(self, chapter, filename):
        content = self.get_chapter_content(chapter)
        with open(filename, 'w', encoding=self.encoding) as f:
            f.write(content)
