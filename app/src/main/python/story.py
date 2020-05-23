import pathlib
import re
import tempfile
import threading
from typing import List, Optional, Dict
from booksite.basesite import Book, Chapter, BaseSite
from bs4 import BeautifulSoup
import functools
import importlib
import requests
import sys
import urllib.parse


class _Download(threading.Thread):
    MAX_THREADING_NUMBER = 50
    complete_count = -1
    sema = None
    lock = None

    @classmethod
    def cls_initial(cls, max_threading_number):
        cls.complete_count = 0
        cls.sema = threading.Semaphore(max_threading_number)
        cls.lock = threading.Lock()

    def __init__(self, action_func, callback_func, *action_func_args):
        assert self.complete_count == 0
        super().__init__()
        self.action_func = action_func
        self.callback_func = callback_func
        self.action_func_args = action_func_args

        self.result = None

    def run(self) -> None:
        if _Download.sema.acquire():
            self.result = self.action_func(*self.action_func_args)
            _Download.sema.release()
            if _Download.lock.acquire():
                _Download.complete_count += 1
                self.callback_func(self.result, self.complete_count)
                _Download.lock.release()

    def get_resuls(self):
        return self.result


class Story:
    FINISH_FLAG_STRING = 'finish'

    def __init__(self):
        self.sites: List[BaseSite] = []
        self.books: List[Book] = []
        self.book_selected: Book = type(None)
        self.chapters: List[Chapter] = []
        self.save_filename = ""
        self.asyn_task_of_fetch_books_statue = ""
        self.asyn_task_of_save_books_statue = ""

    def register_site(self, site: BaseSite) -> None:
        self.sites.append(site)

    # noinspection PyMethodMayBeStatic
    def debug_print_file_path(self, file_path: str) -> None:
        # Android中调用 story.callAttr()不能是static函数
        p = pathlib.Path(file_path)
        print(p.absolute().as_posix())

    def fetch_books(self, search_info: str) -> None:
        assert self.sites
        self.books.clear()
        self.book_selected = None

        def _callback_func(self_, total, results, count):
            self_.books.extend(results)
            self_.asyn_task_of_fetch_books_statue = f"完成{count}/{total}网站搜索"

        _Download.cls_initial(_Download.MAX_THREADING_NUMBER)
        tasks = [_Download(site.get_books, functools.partial(_callback_func, self, len(self.sites)), search_info)
                 for site in self.sites]
        for task in tasks:
            task.start()
        for task in tasks:
            task.join()
        # for task in tasks:
        #     self.books.extend(task.get_resuls())
        self.asyn_task_of_fetch_books_statue = self.FINISH_FLAG_STRING

    def asyn_do_action_fetch_books(self, search_info: str) -> None:
        self.asyn_task_of_fetch_books_statue = "开始查询"
        threading.Thread(target=self.fetch_books, args=(search_info,)).start()

    def asyn_get_statue_fetch_books(self) -> str:
        return self.asyn_task_of_fetch_books_statue

    def choice_book(self, index: int) -> None:
        self.book_selected = self.books[index]

    def fetch_chapters(self):
        book = self.book_selected
        self.chapters = book.site.get_chapters(book)

    @staticmethod
    def fetch_chapter_content(chapter: Chapter):
        return chapter.site.get_chapter_content(chapter)

    def save_books(self, directory) -> None:
        """
        将self.book, self.chapters, self.contents的信息保存为一个zip文件
        """

        def _callback(self_, total, _, count):
            self_.asyn_task_of_save_books_statue = f"完成{count}/{total}章"
            print(f"完成{count}/{total}章")

        book = self.book_selected
        if not book:
            print("请先选择一本书")
            return

        # step1: 如果文件夹不存在，创建
        pathlib.Path(directory).mkdir(parents=True, exist_ok=True)

        # step2: 下载章节列表
        self.fetch_chapters()

        # step3: 创建临时目录，多线程下载内容，保存到临时文件中
        tasks = []
        tmp_dir = tempfile.TemporaryDirectory()  # 创建临时目录
        numbers = len(self.chapters)
        _Download.cls_initial(book.site.site_info.max_threading_number)
        for index in range(numbers):
            chapter = self.chapters[index]
            filename = str(pathlib.Path(tmp_dir.name) / f'{index:05}.txt')
            task = _Download(chapter.site.save_chapter, functools.partial(_callback, self, numbers), chapter, filename)
            tasks.append(task)
        for task in tasks:
            task.start()
        for task in tasks:
            task.join()

        # step4: 将临时目录下的多个文件合并为书籍文件，并删除临时目录
        _format_info = lambda info: re.sub(r'[?*:"<>\\/|]', '', info).strip()
        self.save_filename = f'{directory}{_format_info(book.name)}-{_format_info(book.author)}.txt'
        with open(self.save_filename, 'w', encoding='utf-8') as f:
            files = sorted(list(pathlib.Path(tmp_dir.name).iterdir()))
            for index, file in enumerate(files):
                title = re.sub(r'第.*章', "", self.chapters[index].title).replace('第', '').replace('章', '').strip()
                with open(file.as_posix(), 'r', encoding='utf-8') as f2:
                    f.write(f'\r\n第{index + 1}章 {title}\r\n')
                    f.write(f2.read())
        tmp_dir.cleanup()  # 删除临时目录
        self.asyn_task_of_save_books_statue = self.FINISH_FLAG_STRING

    def asyn_do_action_save_books(self, directory) -> None:
        self.asyn_task_of_save_books_statue = "开始下载书籍"
        threading.Thread(target=self.save_books, args=(directory,)).start()

    def asyn_get_statue_save_books(self) -> str:
        return self.asyn_task_of_save_books_statue


class ManagerSites:
    """判断github上的网站列表是否有变化（增加/删除/更新），并动态更新本地story实例 """
    ignore_files = {"basesite", "__init__"}

    def __init__(self, local_storage_path, remote_site_url, local_temp_storage_path_for_remote_sites):
        """
        :param local_storage_path: 书籍网站的本地存储路径，例如，android下为app本地路径
        :param remote_site_url: github的项目地址
        :param local_temp_storage_path_for_remote_sites: remote_site_url下载到本地的临时地址
        """
        self.local_storage_path = local_storage_path
        self.local_sites = None
        self.remote_site_url = remote_site_url
        self.remote_sites = None
        self.local_temp_storage_path_for_remote_sites = local_temp_storage_path_for_remote_sites

    def _get_version(self, site_file) -> Optional[str]:
        """
        获取网站文件**Site.py中的BaseSite.SiteInfo.version信息
        :return: version 字符串
        """
        with open(site_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # 找到init函数
            if (m := re.search(r'def\s+__init__(.+?)\sdef\s', content, flags=re.DOTALL)) is None:
                return None
            content2 = m.group(1)
            if (m2 := re.search(r'version\s*=\s*[\'\"](.+?)[\'\"]', content2, flags=re.DOTALL)) is None:
                return None
            else:
                return m2.group(1)

    def get_sites_info(self, path) -> Dict:
        p = pathlib.Path(path)
        sites_name_and_path = list((f.stem, f.absolute().as_posix())
                                   for f in p.glob('*Site.py') if f.stem not in self.ignore_files)
        sites_version = [self._get_version(path) for (name, path) in sites_name_and_path]
        sites_info = dict((name, dict(path=path, version=version))
                          for (name, path), version in zip(sites_name_and_path, sites_version))
        return sites_info

    def download_site_file_from_github(self, short_name, url):
        p = pathlib.Path(self.local_temp_storage_path_for_remote_sites)
        r = requests.get(url)
        with open(p / short_name, 'w', encoding='utf-8') as f:
            f.write(r.text)

    def get_remote_sites_from_github(self):
        """

        从github上下载更新文件, 需要将地址
        https://github.com/xiaoping2100/AndroidPyBook/blob/master/app/src/main/python/booksite/CuohengSite.py
        转换为
        https://raw.githubusercontent.com/xiaoping2100/AndroidPyBook/master/app/src/main/python/booksite/CuohengSite.py
        :return:
        """
        github_raw_base_url = 'https://raw.githubusercontent.com/'
        r = requests.get(self.remote_site_url)
        soup = BeautifulSoup(r.content, 'html.parser')
        site_soup_list = soup.select('tbody td.content a')
        sites = [(site.text, urllib.parse.urljoin(github_raw_base_url, site.attrs['href'].replace('/blob/', '/')))
                 for site in site_soup_list if site.text[:-3] not in self.ignore_files]
        for short_name, url in sites:
            self.download_site_file_from_github(short_name, url)

    def check_update(self) -> List:
        self.get_remote_sites_from_github()
        self.local_sites = self.get_sites_info(self.local_storage_path)
        self.remote_sites = self.get_sites_info(self.local_temp_storage_path_for_remote_sites)
        update_list = []
        for site_name, remote_site_info in self.remote_sites:
            if site_name in self.local_sites and remote_site_info['version'] == self.local_sites[site_name]['version']:
                continue
            update_list.append((site_name, self.local_sites[site_name]['path'], remote_site_info['path']))
        return update_list

    def update_local(self) -> None:
        pass

    def update_story_instance(self, story: Story) -> None:
        pass
