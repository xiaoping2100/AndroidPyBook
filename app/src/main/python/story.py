import pathlib
import re
import shutil
import tempfile
import threading
from typing import List
from booksite.basesite import Book, Chapter, BaseSite
import functools
import importlib
import requests
import sys
import xml.dom.minidom


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
        for i, site_ in enumerate(self.sites):
            if site_.site_info.name == site.site_info.name:
                self.sites[i] = site
                break
        else:
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

    def __init__(self, local_storage_path, site_remote_url_base, local_temp_storage_path_for_remote_sites):
        """
        :param local_storage_path: 书籍网站的本地存储路径，例如，android下为app本地路径
        :param remote_site_url: github项目书源更新信息的url地址
        :param local_temp_storage_path_for_remote_sites: remote_site_url下载到本地的临时地址
        """
        self.basesite_filename = "basesite.py"
        self.booksites_list_filename = "booksites_list.xml"
        self.local_storage_path = local_storage_path
        self.local_sites = None
        self.site_remote_url_base = site_remote_url_base
        self.remote_sites = None
        self.temp_storage_path = local_temp_storage_path_for_remote_sites
        self.update_site_dict = {}

    def download_site_file_from_github(self, full_name_path, url):
        r = requests.get(url)
        with full_name_path.open('w', encoding='utf-8') as f:
            f.write(r.text)

    @staticmethod
    def get_site_infos(site_filename):
        """
        从booksites_list.xml文件中获取书源信息，包括网站名称，版本和url地址
        返回值：
            all_site_list： 所有的网站信息
            app_site_list： app安装时自带的网站信息

        """

        def data(site, tagname):
            try:
                return site.getElementsByTagName(tagname)[0].childNodes[0].data.strip()
            except:
                pass

        doc = xml.dom.minidom.parse(site_filename)
        booksites_root = doc.documentElement
        all_booksites_root = booksites_root.getElementsByTagName('all_booksites')[0]
        app_booksites_root = booksites_root.getElementsByTagName('app_booksites')[0]
        all_sites = all_booksites_root.getElementsByTagName('booksite')
        app_sites = app_booksites_root.getElementsByTagName('booksite')

        all_site_dict = dict(
            (data(i, 'classname'), dict(name=data(i, 'name'), url=data(i, 'url'), version=data(i, 'version')))
            for i in all_sites)
        app_site_dict = dict(
            (data(i, 'classname'), dict(name=data(i, 'name'), url=data(i, 'url'), version=data(i, 'version')))
            for i in app_sites)
        return all_site_dict, app_site_dict

    def check_update(self):
        """
        从github上下载更新文件,注意地址为https://raw.githubusercontent.com开头
        例如：https://raw.githubusercontent.com/xiaoping2100/AndroidPyBook/master/app/src/main/python/booksite/CuohengSite.py
        :return:
        """

        # github_raw_base_url = 'https://raw.githubusercontent.com/'
        # 下载更新列表，保持到临时目录
        remote_filename = pathlib.Path(self.temp_storage_path) / self.booksites_list_filename
        self.download_site_file_from_github(remote_filename, self.site_remote_url_base + self.booksites_list_filename)
        remote_site_dict, remote_site_dict2 = self.get_site_infos(remote_filename.absolute().as_posix())

        local_filename = pathlib.Path(self.local_storage_path) / self.booksites_list_filename
        if local_filename.exists():
            local_site_dict, _ = self.get_site_infos(local_filename.absolute().as_posix())
        else:
            local_site_dict = remote_site_dict2

        self.update_site_dict.clear()
        for classname, value in remote_site_dict.items():
            name, version, url = value['name'], value['version'], value['url']
            if classname in local_site_dict and float(version) <= float(local_site_dict[classname]['version']):
                continue
            self.update_site_dict[classname] = dict(version=version, url=url, name=name)

    def update_local(self) -> None:
        # 拷贝更新的site文件
        for classname, value in self.update_site_dict.items():
            try:
                filename = classname + '.py'
                self.download_site_file_from_github(pathlib.Path(self.local_storage_path) / filename, value['url'])
                self.update_site_dict[classname]['statue'] = True
            except Exception as e:
                print(e)
                self.update_site_dict[classname]['statue'] = False

        # 拷贝basesie.py文件
        self.download_site_file_from_github(pathlib.Path(self.local_storage_path) / self.basesite_filename,
                                            self.site_remote_url_base + self.basesite_filename)

        # 拷贝booksites_list.xml文件
        shutil.copy(pathlib.Path(self.temp_storage_path) / self.booksites_list_filename,
                    pathlib.Path(self.local_storage_path) / self.booksites_list_filename, )

    def update_story_instance(self, story: Story) -> None:
        # 动态加载LocalBookSite下的文件,实验通过，但是pycharm会报错
        if self.local_storage_path not in sys.path:
            sys.path.append(self.local_storage_path)
        # p = pathlib.Path(self.local_storage_paths)
        for classname, value in self.update_site_dict.items():
            if value['statue']:
                try:
                    new_pkg = importlib.import_module(classname)
                    new_site = getattr(new_pkg, classname)()
                    story.register_site(new_site)
                    print(f'加载{classname}成功，版本号为{new_site.site_info.version}')
                except Exception as e:
                    print(f'加载{classname}失败，错误信息为', e)
