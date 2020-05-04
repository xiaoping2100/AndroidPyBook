import time
import tkinter
import tkinter.messagebox
import story
import booksite


class Application(tkinter.Frame):
    """
    <Button-1>        　  　鼠标左键按下，2表示中键，3表示右键；
    <ButtonPress-1>    　   同上；
    <ButtonRelease-1>　　　 鼠标左键释放；
    <B1-Motion>  　　       按住鼠标左键移动；
    <Double-Button-1>  　　 双击左键；
    <Enter>       　　      鼠标指针进入某一组件区域；
    <Leave>    　　         鼠标指针离开某一组件区域；
    <MouseWheel>  　   　　 滚动滚轮；
    <KeyPress-A> 　　  　　  按下A键，A可用其他键替代；
    <Alt-KeyPress-A>　　　   同时按下alt和A；alt可用ctrl和shift替代；
    <Double-KeyPress-A>　　  快速按两下A；
    <Lock-KeyPress-A>　　　  大写状态下按A；
    """

    def __init__(self, root: tkinter.Tk, story_: story.Story):
        super().__init__(root)
        self.root = root
        self.story_ = story_
        self.query_info_var = tkinter.StringVar()
        self.query_info_var.set('某某宝')
        self.download_var = tkinter.StringVar()
        self.download_var.set('未开始下载')
        self.download_text: tkinter.Entry = type(None)
        self.ret_books = type(None)
        self.book_brief = type(None)
        self.ret_chapters = type(None)
        self.ret_content = type(None)
        self.create_widgets()

    def create_widgets(self):
        query_label = tkinter.Label(self.root, text='输入查询的书名或作者:', width=20)
        query_input = tkinter.Entry(self.root, textvariable=self.query_info_var, width=120)
        query_books_btn = tkinter.Button(self.root, text='查询', command=self.query_books)

        ret_label2 = tkinter.Label(self.root, text='查询书籍结果:', width=20)
        self.ret_books = tkinter.Listbox(self.root, selectmode=tkinter.SINGLE, height=10, width=120)

        ret_label3 = tkinter.Label(self.root, text='书籍详细信息:', width=20)
        self.book_brief = tkinter.Text(self.root, height=5, width=120)
        query_chapters_btn = tkinter.Button(self.root, text='查询章节信息', command=self.query_chapters)

        ret_label4 = tkinter.Label(self.root, text='书籍章节信息:', width=20)
        self.ret_chapters = tkinter.Listbox(self.root, selectmode=tkinter.SINGLE, height=10, width=120)
        query_content_btn = tkinter.Button(self.root, text='查询小说信息', command=self.query_content)

        ret_label5 = tkinter.Label(self.root, text='小说信息:', width=20)
        self.ret_content = tkinter.Text(self.root, height=25, width=120)

        # download_label = tkinter.Label(self.root, text='下载进度:')
        # self.download_text = tkinter.Entry(self.root, textvariable=self.download_var, width=120)
        download_book_btn = tkinter.Button(self.root, text='下载', command=self.download_book)

        query_label.grid(row=1, column=1)
        query_input.grid(row=1, column=2)
        query_books_btn.grid(row=1, column=3)

        ret_label2.grid(row=2, column=1)
        self.ret_books.grid(row=2, column=2)

        ret_label3.grid(row=3, column=1)
        self.book_brief.grid(row=3, column=2)
        query_chapters_btn.grid(row=3, column=3)

        ret_label4.grid(row=4, column=1)
        self.ret_chapters.grid(row=4, column=2)
        query_content_btn.grid(row=4, column=3)

        ret_label5.grid(row=5, column=1)
        self.ret_content.grid(row=5, column=2)

        # download_label.grid(row=6, column=1)
        # self.download_text.grid(row=6, column=2)
        download_book_btn.grid(row=6, column=3)

        # 单击事件
        self.ret_books.bind('<ButtonRelease-1>', self.select_book)

    def query_books(self):
        self.ret_books.delete(0, "end")
        info = self.query_info_var.get()
        self.story_.fetch_books(info)

        self.ret_books.delete(0, "end")
        for book in self.story_.books:
            item = f'书名:{book.name} 作者：{book.author} 简介：{book.brief[:60]}'
            self.ret_books.insert('end', item[:40])

    def query_chapters(self):
        sel = self.ret_books.curselection()
        if not sel:
            return
        self.story_.choice_book(sel[0])
        self.story_.fetch_chapters()

        self.ret_chapters.delete(0, "end")
        for chapter in self.story_.chapters:
            self.ret_chapters.insert('end', chapter.title)

    def query_content(self):
        sel = self.ret_chapters.curselection()
        if not sel:
            return
        content = self.story_.fetch_chapter_content(self.story_.chapters[sel[0]])
        self.ret_content.delete('1.0', 'end')
        if content:
            self.ret_content.insert('insert', content)
        else:
            self.ret_content.insert('insert', '访问失败')

    def select_book(self, _):
        if not self.story_.books:
            return
        sel = self.ret_books.curselection()
        if not sel:
            return
        self.book_brief.delete('1.0', 'end')
        info = self.story_.books[sel[0]].brief
        self.book_brief.insert('insert', info)

    def download_book(self):
        start = time.time()
        self.story_.save_books('d:\\temp\\')
        tkinter.messagebox.showinfo('提示', f'耗时:{time.time() - start}秒')


def main():
    story_ = story.Story()
    site1 = booksite.XqishutaSite()
    story_.register_site(site1)
    site2 = booksite.SoxsSite()
    story_.register_site(site2)
    site3 = booksite.CuohengSite()
    story_.register_site(site3)
    site4 = booksite.Shuku87Site()
    story_.register_site(site4)
    site5 = booksite.Fox2018Site()
    story_.register_site(site5)
    site6 = booksite.DaocaorenshuwuSite()
    story_.register_site(site6)

    root = tkinter.Tk()
    root.title('下载小说')
    root.geometry('1440x900')
    app = Application(root=root, story_=story_)
    app.mainloop()


if __name__ == "__main__":
    main()
