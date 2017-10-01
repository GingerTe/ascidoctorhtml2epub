import os
import re
from uuid import uuid4

import lxml.html as html
from ebooklib import epub
from ebooklib.plugins.base import BasePlugin
from lxml import etree
from lxml.html import HtmlElement

ROOT_DIR = r'C:\Users\Kwert\PycharmProjects\asciidoctor2epub\progit2-ru-master'
FILE_TO_PARSE = 'progit.html'
RES_NAME = 'Pro Git'
HREF = {}
AUTHORS = 'Scott Chacon', 'Ben Straub'
SUBJECTS = 'Программирование', 'Git'


class ConvertObjectToString(BasePlugin):
    NAME = 'Replace HtmlElement to string'

    def html_before_write(self, book, chapter):
        if isinstance(chapter.content, HtmlElement):
            chapter.content = etree.tostring(chapter.content, encoding='utf-8').decode()


class FixIds(BasePlugin):
    NAME = 'Fix incorrect id and links'

    def html_before_write(self, book, chapter):
        if chapter.content:
            # raise Exception(HREF)
            for old_id, new_id in HREF.items():
                chapter.content = re.sub(' href="%s"' % old_id, ' href="%s"' % new_id, chapter.content)


class FixFontAwesome(BasePlugin):
    NAME = 'Fix FontAwesome classes'

    def html_before_write(self, book, chapter):
        if chapter.content:
            # raise Exception(chapter.content)
            chapter.content = re.sub(
                '<div class="admonitionblock ([^"]+)">[\S\s]+?'
                '<td class="content">([\s\S]+?)</td>'
                '[\S\s]+?\s+</table>\s+</div>',
                lambda m: """<aside class="admonition %s" title="%s" epub:type="note">
                                <div class="content">
                                %s
                                </div>
                            </aside>""" % (m.group(1), m.group(1), m.group(2)),
                chapter.content)


def parse_root():
    book = epub.EpubBook()
    book.set_language('ru')
    book.spine = ['cover', 'nav']

    book.set_cover('images/cover.png', open(os.path.join(*(ROOT_DIR, 'book', 'cover.png')), 'rb').read())

    o_page = html.parse(os.path.join(ROOT_DIR, FILE_TO_PARSE))  # type: HtmlElement
    o_toc = o_page.xpath('//*[@id="toc"]')[0]  # type: HtmlElement

    for index, o_section in enumerate(o_toc.xpath('./ul/li'), 1):  # type: int, HtmlElement
        section_id, section_name = add_toc(book.toc, o_section, index)

        o_section_body = o_page.xpath("//*[@id='%s']/.." % section_id)[0]  # type: HtmlElement
        c0 = epub.EpubHtml(uid=section_id if not section_id.startswith('_') else section_id[1:],
                           file_name='section_%s.xhtml' % section_name, lang='ru', content=o_section_body)
        book.add_item(c0)

        book.spine.append(c0)

        get_all_ids(c0)

        write_img(book, o_section_body)

        c0.add_link(href='styles/epub3.css', rel="stylesheet", type="text/css")
        c0.add_link(href='styles/epub3-css3-only.css', media="(min-device-width: 0px)", rel="stylesheet",
                    type="text/css")

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    for author in AUTHORS:
        book.add_author(author, uid='a' + str(uuid4())[:7], role='aut')

    book.set_title(RES_NAME)

    book.guide.extend([
        {
            'href': 'section_01.xhtml',
            'title': 'section_01',
            'type': 'text'
        },
        {
            'href': 'cover.xhtml',
            'title': 'cover',
            'type': 'cover'
        }
    ])
    # print(book.toc)
    nav = book.get_item_with_id('nav')
    nav.add_link(href='styles/epub3.css', rel="stylesheet", type="text/css")
    nav.add_link(href='styles/epub3-css3-only.css', media="(min-device-width: 0px)", rel="stylesheet", type="text/css")

    add_styles(book)
    for subject in SUBJECTS:
        book.add_metadata('DC', 'subject', subject)
    opts = {'plugins': [ConvertObjectToString(),
                        FixIds(),
                        FixFontAwesome()],
            'epub3_landmark': False}
    epub.write_epub('%s.epub' % RES_NAME, book, opts)


def add_toc(toc, o_section, index):
    o_section_href = o_section.xpath('a')[0]

    section_id = o_section_href.get('href')[1:]

    section_name = str(index).zfill(2)
    toc.append(epub.Link('section_%s.xhtml' % section_name, o_section_href.text_content(),
                         section_id if not section_id.startswith('_') else section_id[1:]))

    if o_section.xpath('ul/li'):
        toc[-1] = [toc[-1]]
        toc[-1].append([])
    for el in o_section.xpath('ul/li'):
        add_toc(toc[-1][-1], el, index)

    return section_id, section_name


def add_styles(book):
    fonts_dir = os.path.join(*(os.path.dirname(__file__), 'data', 'fonts'))
    for item in os.listdir(fonts_dir):
        book.add_item(epub.EpubItem(content=open(os.path.join(fonts_dir, item), 'rb').read(),
                                    file_name="fonts/%s" % item,
                                    media_type='application/x-font-truetype'))

    styles_dir = os.path.join(*(os.path.dirname(__file__), 'data', 'styles'))
    for item in os.listdir(styles_dir):
        book.add_item(epub.EpubItem(content=open(os.path.join(styles_dir, item), 'rb').read(),
                                    file_name="styles/%s" % item,
                                    media_type='text/css'))


def get_all_ids(section):
    """Get all id from section and write it to global dict
    Use it to fix incorrect href
    """
    global HREF
    for el in section.content.xpath(".//*[@id]"):
        el_id = el.get('id')
        old_href = "#%s" % el_id
        if el_id.startswith('_'):
            el_id = el_id[1:]
            el.set('id', el_id)
        HREF[old_href] = '%s#%s' % (section.file_name, el_id)


def write_img(book, section):
    """
    Write images from section to result epub
    :param book: epub.EpubBook
    :type section: HtmlElement
    """
    for img in section.xpath('.//img'):
        src = img.get('src')
        image_element = epub.EpubItem(
            file_name=src,
            content=open(os.path.join(ROOT_DIR, src), 'rb').read())
        book.add_item(image_element)


if __name__ == '__main__':
    from time import clock

    clock()

    parse_root()
    print(clock())
