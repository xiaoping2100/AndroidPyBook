import copy
import re

import chardet
import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import List

try:
    import basesite
except (ModuleNotFoundError, ImportError) as e:
    from . import basesite


class Shuku87Site(basesite.BaseSite):
    def __init__(self):
        self.site_info = basesite.SiteInfo(
            type='网络小说',
            statue='上线版本',
            url='http://www.87xiaoshuo.net',
            name='霸气书库',
            brief_name='霸气网',
            version='1.1',
            max_threading_number=3,
        )
        super().__init__(self.site_info)
        self.base_url = 'http://www.87xiaoshuo.net'
        self.encoding = 'GB2312'
        self.search_url = 'http://www.87xiaoshuo.net/modules/article/search.php'
        self.session = requests.session()

    @basesite.print_in_out
    def get_books(self, search_info: str) -> List[basesite.Book]:
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                   'Content-Type': 'application/x-www-form-urlencoded',
                   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:75.0) Gecko/20100101 Firefox/75.0'}
        # data = {'t': '1', 'searchkey': urllib.parse.quote(search_info.encode('GB2312'))} # 错误
        data = f'searchkey={urllib.parse.quote(search_info.encode("GB2312"))}&t=1'
        r = self.try_post_url(self.session, url=self.search_url, try_timeout=5,
                              headers=headers, data=data, allow_redirects=False)
        if r is None:
            return []
        if r.status_code == 302:  # 只找到一本书，将跳转
            return [basesite.Book(site=self, url=r.headers['Location'], name=search_info, author="", brief="")]

        soup = BeautifulSoup(r.content.decode(self.encoding, 'ignore'), 'html.parser')
        if not (book_soup_list := soup.select('div.ml212 dt')):
            return []

        search_book_results = []
        for book_soup in book_soup_list:
            book_url = book_soup.select_one('a').attrs['href']
            m = re.search(r'(\w+).*作者：(\w+).*?(\w+.*)$', book_soup.text, flags=re.DOTALL)
            if not m:
                print(f'error in {self.site_info.brief_name} {book_url=} {book_soup.text=}')
                return []
            book_name = m.group(1)
            book_author = m.group(2)
            book_brief = m.group(3).replace("\n", "").replace("\r", "").strip()
            book = basesite.Book(site=self, url=book_url, name=book_name, author=book_author,
                                 brief=book_brief)
            search_book_results.append(book)
        return search_book_results

    @basesite.print_in_out
    def get_chapters(self, book: basesite.Book) -> List[basesite.Chapter]:
        url = book.url.replace("/book/", "/read/")
        r = self.try_get_url(self.session, url)
        if r is None:
            return []

        soup = BeautifulSoup(r.content.decode(self.encoding, 'ignore'), 'html.parser')
        chapter_soup_list = soup.select('td > a')
        chapters = [basesite.Chapter(site=self,
                                     url=self.base_url + chapter.attrs['href'],
                                     title=chapter.text)
                    for chapter in chapter_soup_list]
        return chapters

    def get_chapter_content(self, chapter: basesite.Chapter) -> str:
        session = copy.deepcopy(self.session)
        r = self.try_get_url(session, chapter.url)
        session.close()
        if r is None:
            return f'{chapter.title}\r\n下载失败'

        text = r.content.decode(self.encoding, 'ignore')
        soup = BeautifulSoup(text, 'html.parser')
        if (content_soup := soup.select_one('div#content')) is None:
            print(f'error in get_chapter_content{chapter=}')
            content = text.strip()
        else:
            content = content_soup.text.strip()
        # title = chapter.title if chapter.title.startswith("第") else f"第{chapter.title}"
        # content2 = f'\r\n{title}\r\n{content.strip()}'
        return content

    def save_chapter(self, chapter, filename):
        content = self.get_chapter_content(chapter)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
