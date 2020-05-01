import story
import booksite


def main():
    story_ = story.Story()
    site1 = booksite.XqishutaSite()
    story_.register_site(site1)
    site2 = booksite.XqishutaSite()
    story_.register_site(site2)
    # site2 = SoxsSite()
    # story.register_site(site2)
    return story_
