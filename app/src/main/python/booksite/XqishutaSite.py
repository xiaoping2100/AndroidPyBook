import copy
import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import List

try:
    import basesite
except (ModuleNotFoundError, ImportError) as e:
    print(type(e), e)
    from . import basesite


class XqishutaSite(basesite.BaseSite):
    def __init__(self):
        self.site_info = basesite.SiteInfo(
            type='网络小说',
            statue='上线版本',
            url='http://www.xqishuta.com',
            name='奇书网',
            brief_name='奇书网',
            version='1.1',
            max_threading_number=50,
        )
        super().__init__(self.site_info)
        self.site_url = 'http://www.xqishuta.com'
        self.encoding = 'utf-8'
        self.search_url = 'http://www.xqishuta.com/search.html?searchkey=%s'
        self.session = requests.session()

    @basesite.print_in_out
    def get_books(self, search_info: str) -> List[basesite.Book]:
        url = self.search_url % urllib.parse.quote(search_info)
        r = self.try_get_url(self.session, url, try_timeout=5)
        if r is None:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        book_tag_list = soup.select('tr')
        book_num = len(book_tag_list) - 1
        if book_num == 0:
            return []

        search_book_results = []
        book_soup_list = book_tag_list[1:]
        for book_soup in book_soup_list:
            td_list = book_soup.findAll('td')
            book_url = self.site_url + td_list[1].find('a').attrs['href']
            book_name = td_list[1].find('a').text
            book_author = td_list[2].text
            book_brief = f"最新章节:{td_list[3].find('a').text} 更新时间:{td_list[4].text.strip()}"
            book = basesite.Book(site=self, url=book_url, name=book_name, author=book_author,
                                 brief=book_brief)
            search_book_results.append(book)
        return search_book_results

    @basesite.print_in_out
    def get_chapters(self, book: basesite.Book) -> List[basesite.Chapter]:
        r = self.try_get_url(self.session, book.url)
        if r is None:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        real_url = self.site_url + soup.select_one('div.detail_right').select_one('a').attrs['href']
        r = self.session.get(real_url)
        soup = BeautifulSoup(r.content, 'html.parser')

        chapter_soup_list = soup.select('div#info>div.pc_list')[1].select('ul>li')
        chapters = [basesite.Chapter(site=self,
                                     url=real_url + chapter.select_one('a').attrs['href'],
                                     title=chapter.select_one('a').text)
                    for chapter in chapter_soup_list]
        return chapters

    def get_chapter_content(self, chapter: basesite.Chapter) -> str:
        session = copy.deepcopy(self.session)
        r = self.try_get_url(session, chapter.url)
        session.close()
        if r is None:
            return f'{chapter.title}\r\n下载失败'

        soup = BeautifulSoup(r.content, 'html.parser')
        content_soup = soup.select_one('div#content1')
        for i in content_soup.select('p.sitetext'):
            i.decompose()
        content = content_soup.text.strip()
        # title = chapter.title if chapter.title.startswith("第") else f"第{chapter.title}"
        # content = f'\r\n{title}\r\n{content.replace("最新网址：www.xqishuta.com", "").strip()}'
        return content

    def save_chapter(self, chapter, filename):
        content = self.get_chapter_content(chapter)
        with open(filename, 'w', encoding=self.encoding) as f:
            f.write(content)
