import pathlib
import tempfile
import time
import threading
from typing import List
from booksite.basesite import Book, Chapter, BaseSite
import functools


class Story:
    def __init__(self):
        self.sites: List[BaseSite] = []
        self.books: List[Book] = []
        self.book_selected: Book = type(None)
        self.chapters: List[Chapter] = []
        self.save_filename = ""
        self.asyn_task_of_save_books = None
        self.asyn_task_of_save_books_statue = ""
        self.asyn_task_of_fetch_books = None

    def register_site(self, site: BaseSite) -> None:
        self.sites.append(site)

    def prepare_fetch_books(self):
        assert self.sites
        self.books.clear()
        self.book_selected = None

    def fetch_books(self, search_info: str) -> None:
        """仅wintk使用"""
        self.prepare_fetch_books()
        for site in self.sites:
            self.books.extend(site.get_books(search_info))

    def asyn_fetch_books(self, search_info: str) -> None:
        self.asyn_task_of_fetch_books = threading.Thread(target=self.fetch_books,
                                                         args=(search_info,))
        self.asyn_task_of_fetch_books.start()

    def asyn_get_statue_fetch_books(self) -> str:
        if self.asyn_task_of_fetch_books.is_alive():
            return "查询中.."
        else:
            self.asyn_task_of_fetch_books = None
        return "finish"

    def choice_book(self, index: int) -> None:
        self.book_selected = self.books[index]

    def fetch_chapters(self):
        book = self.book_selected
        self.chapters = book.site.get_chapters(book)

    @staticmethod
    def fetch_chapter_content(chapter: Chapter):
        return chapter.site.get_chapter_content(chapter)

    def save_books_10chapeters(self, directory) -> None:
        """wintk使用，只保存前五章和最后五章内容，用于测试网站脚本是否正确"""

    def save_books(self, directory) -> None:
        """
        将self.book, self.chapters, self.contents的信息保存为一个zip文件
        """
        sema = threading.Semaphore(50)
        lock = threading.Lock()
        complete_count = 0

        def _down(func, cb, *args):
            nonlocal sema, lock, complete_count
            if sema.acquire():
                ret = func(*args)
                sema.release()
                if lock.acquire():
                    complete_count += 1
                    cb(complete_count)
                    lock.release()
                return ret

        def _callback(self_, total, count):
            self_.asyn_task_of_save_books_statue = f"完成{count}/{total}章"

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
        for index in range(numbers):
            chapter = self.chapters[index]
            filename = str(pathlib.Path(tmp_dir.name) / f'{index:05}.txt')
            task = threading.Thread(target=_down, args=(chapter.site.save_chapter,
                                                        functools.partial(_callback, self, numbers),
                                                        chapter, filename,))
            tasks.append(task)
        for task in tasks:
            task.start()
        while complete_count < numbers:
            time.sleep(0.1)

        self.save_filename = f'{directory}{book.name}-{book.author}.txt'

        # step4: 将临时目录下的多个文件合并为书籍文件，并删除临时目录
        with open(self.save_filename, 'w', encoding='utf-8') as f:
            files = sorted(list(pathlib.Path(tmp_dir.name).iterdir()))
            for file in files:
                with open(file.as_posix(), 'r', encoding='utf-8') as f2:
                    f.write(f2.read())
        tmp_dir.cleanup()  # 删除临时目录
        self.asyn_task_of_save_books_statue = "finish"

    def asyn_do_action_save_books(self, directory) -> None:
        self.asyn_task_of_save_books_statue = "开始下载书籍"
        self.asyn_task_of_save_books = threading.Thread(target=self.save_books, args=(directory,))
        self.asyn_task_of_save_books.start()

    def asyn_get_statue_save_books(self) -> str:
        statue = self.asyn_task_of_save_books_statue
        if statue == "finish":
            self.asyn_task_of_save_books = None
        return statue
