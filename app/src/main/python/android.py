import story
import booksite


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
    return story_
