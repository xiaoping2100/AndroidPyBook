import copy
import itertools
import re
import threading
import html5lib

import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import List

from .basesite import SiteInfo, BaseSite, Book, Chapter


class DaocaorenshuwuSite(BaseSite):
    def __init__(self):
        self.site_info = SiteInfo(
            type='文学',
            statue='上线版本',
            url='https://www.daocaorenshuwu.com',
            name='稻草人书屋',
            brief_name='稻草人',
            max_threading_number=10,  # 每个chapter会进行多线程下载(get_chapter_content)，所以总线程数量设置为10
        )
        super().__init__(self.site_info)
        self.base_url = 'https://www.daocaorenshuwu.com'
        self.encoding = 'utf-8'
        self.search_url = 'https://www.daocaorenshuwu.com/plus/search.php?q=%s'
        self.session = requests.session()

    def get_books(self, search_info: str) -> List[Book]:
        url = self.search_url % urllib.parse.quote(search_info)
        r = self.try_get_url(self.session, url, try_timeout=5)

        soup = BeautifulSoup(r.content, 'html.parser')
        book_soup_list = soup.select('tbody > tr')
        search_book_results = []
        for book_soup in book_soup_list:
            td_soup_list = book_soup.select('td')
            book_url = self.base_url + td_soup_list[0].select_one('a').attrs['href']
            if book_url.find('search.html') != -1:
                continue
            book_name = td_soup_list[0].text
            book_author = td_soup_list[1].text
            book_brief = "无"
            book = Book(site=self, url=book_url, name=book_name, author=book_author,
                        brief=book_brief)
            search_book_results.append(book)
        return search_book_results

    def get_chapters(self, book: Book) -> List[Chapter]:
        r = self.try_get_url(self.session, book.url)
        if r is None:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        chapter_soup_list = soup.select('div#all-chapter div.panel-body div.item a')
        chapters = [Chapter(site=self,
                            url='https:' + chapter.attrs['href'],
                            title=chapter.text)
                    for chapter in chapter_soup_list]
        return chapters

    def get_chapter_content(self, chapter: Chapter) -> str:
        class _InnerDown(threading.Thread):
            def __init__(self, func, session_, url):
                super().__init__()
                self.func = func
                self.session = copy.deepcopy(session_)
                self.url = url
                self.r = None

            def run(self) -> None:
                self.r = self.func(self.session, self.url)
                self.session.close()

        session = copy.deepcopy(self.session)
        partial_url = chapter.url[:-5]

        # step1: 先下载第一页和第二页, 判断总共多少页
        tasks = [_InnerDown(self.try_get_url, session, chapter.url),
                 _InnerDown(self.try_get_url, session, partial_url + "_2.html")]
        for task in tasks:
            task.start()
        for task in tasks:
            task.join()
        r1, r2 = tasks[0].r, tasks[1].r
        if r1 is None:
            session.close()
            return f'\r\n{chapter.title}\r\n下载失败'

        soup1 = BeautifulSoup(r1.content, 'html5lib')  # 文档格式有错误，不能使用速度较快的html.parser
        has_multipages = False
        try:
            if soup1.select('div.text-center')[0].select('button.btn-info')[2].text.find('下一页') >= 0:
                has_multipages = True
        except IndexError:
            pass

        if has_multipages:
            if r2 is None:
                session.close()
                return f'\r\n{chapter.title}\r\n下载失败'
            soup2 = BeautifulSoup(r2.content, 'html5lib')
            page_info = soup2.select_one('div.book-type li.active').text
            pages = int(re.search(r'/(\d+)页）', page_info).group(1))
            soup_list = [soup1, soup2]
        else:
            pages = 1
            soup_list = [soup1]

        # step2: 多线程下载
        url_list = ([f'{partial_url}_{i}.html' for i in range(3, pages + 1)])
        tasks = [_InnerDown(self.try_get_url, session, url) for url in url_list]
        for task in tasks:
            task.start()
        for task in tasks:
            task.join()
        session.close()
        for task in tasks:
            if task.r is None:
                return f'\r\n{chapter.title}\r\n下载失败'
            else:
                soup_list.append(BeautifulSoup(task.r.content, 'html5lib'))

        # step3: 合并下载内容
        content_list = []
        for soup in soup_list:
            content_soup = soup.select_one('div#cont-text')
            for i in content_soup.select('script,style,[class]'):
                i.decompose()
            content_list.append(content_soup.text.strip())
        # return f'\r\n{chapter.title}\r\n{"".join(content_list)}'
        return "\r\n".join(content_list)

    def save_chapter(self, chapter, filename):
        content = self.get_chapter_content(chapter)
        with open(filename, 'w', encoding=self.encoding) as f:
            f.write(content)
