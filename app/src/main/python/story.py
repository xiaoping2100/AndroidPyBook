import pathlib
import tempfile
import threading
from typing import List
from booksite.basesite import Book, Chapter, BaseSite
import functools


class _Download(threading.Thread):
    MAX_THREADING_NUMBER = 50
    complete_count = -1
    sema = None
    lock = None

    @classmethod
    def cls_initial(cls):
        cls.complete_count = 0
        cls.sema = threading.Semaphore(cls.MAX_THREADING_NUMBER)
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
                self.callback_func(self.complete_count)
                _Download.lock.release()

    def get_resuls(self):
        return self.result


class Story:
    MAX_THREADING_NUMBER = 50
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

    def fetch_books(self, search_info: str) -> None:
        assert self.sites
        self.books.clear()
        self.book_selected = None

        def _callback(self_, total, count):
            self_.asyn_task_of_fetch_books_statue = f"完成{count}/{total}网站搜索"

        _Download.cls_initial()
        tasks = [_Download(site.get_books, functools.partial(_callback, self, len(self.sites)), search_info)
                 for site in self.sites]
        for task in tasks:
            task.start()
        for task in tasks:
            task.join()
        for task in tasks:
            self.books.extend(task.get_resuls())
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

        def _callback(self_, total, count):
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
        _Download.cls_initial()
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
        self.save_filename = f'{directory}{book.name}-{book.author}.txt'
        with open(self.save_filename, 'w', encoding='utf-8') as f:
            files = sorted(list(pathlib.Path(tmp_dir.name).iterdir()))
            for file in files:
                with open(file.as_posix(), 'r', encoding='utf-8') as f2:
                    f.write(f2.read())
        tmp_dir.cleanup()  # 删除临时目录
        self.asyn_task_of_save_books_statue = self.FINISH_FLAG_STRING

    def asyn_do_action_save_books(self, directory) -> None:
        self.asyn_task_of_save_books_statue = "开始下载书籍"
        threading.Thread(target=self.save_books, args=(directory,)).start()

    def asyn_get_statue_save_books(self) -> str:
        return self.asyn_task_of_save_books_statue
