import bs4
import demjson
import sys
import urllib.request
import urllib.parse
from dateutil.parser import parse
import re
import html
import pprint
import rssit.util
import datetime


# for news1: http://news1.kr/search_front/search.php?query=[...]&collection=front_photo&startCount=[0,20,40,...]
# for starnews: http://star.mt.co.kr/search/index.html?kwd=[...]&category=PHOTO
# for articleList-based: http://stardailynews.co.kr/news/articleList.html?page=1&sc_area=A&sc_word=[...]&view_type=sm
# for tvdaily: http://tvdaily.asiae.co.kr/searchs.php?section=17&searchword=[...]&s_category=2


# http://stackoverflow.com/a/18359215
def get_encoding(soup):
    encod = soup.find("meta", charset=True)
    if encod:
        return encod["charset"]

    encod = soup.find("meta", attrs={'http-equiv': "Content-Type"})
    if not encod:
        encod = soup.find("meta", attrs={"Content-Type": True})

    if encod:
        content = encod["content"]
        match = re.search('charset *= *(.*)', content, re.IGNORECASE)
        if match:
            return match.group(1)

    raise ValueError('unable to find encoding')


def get_redirect(myjson, soup):
    refreshmeta = soup.find("meta", attrs={"http-equiv": "refresh"})
    if refreshmeta:
        content = refreshmeta["content"]
        url = re.sub(r".*?url=(.*?)", "\\1", content)
        if url != content:
            return url
    return None


def strify(x):
    if type(x) is list:
        nx = []
        for i in x:
            nx.append(strify(i))
        return nx
    if type(x) is dict:
        nx = {}
        for i in x:
            nx[strify(i)] = strify(x[i])
    if type(x) in [float, int]:
        return x
    elif x:
        return str(x)
    else:
        return x


def get_url(config, url):
    base = "/url/"
    if url.startswith("quick:"):
        base = "/qurl/"
        url = url[len("quick:"):]

    if url.startswith("//"):
        url = url[len("//"):]

    url = re.sub(r"^[^/]*://", "", url)

    regexes = [
        "entertain\.naver\.com/",
        "find\.joins\.com/",
        "isplus\.joins\.com/",
        "news1.kr/search_front/",
        "topstarnews.net/search.php",
        "star\.mt\.co\.kr/search",
        "osen\.mt\.co\.kr/search",
        "stardailynews\.co\.kr/news/articleList",
        "liveen.co.kr/news/articleList",
        "tvdaily\.asiae\.co\.kr/searchs",
        "chicnews\.mk\.co\.kr/searchs",
        "search\.hankyung\.com",
        "search\.chosun\.com",
        "mydaily.co.kr/.*/search",
        "search.mbn.co.kr",
        "newsen\.com",
        "xportsnews\.com",
        "munhwanews\.com",
        "dispatch.co.kr",
    ]

    found = False
    for regex in regexes:
        match = re.search(regex, url)
        if match:
            found = True

    if not found:
        return None

    return base + url


def get_selector(soup, selectors, *args, **kwargs):
    tag = None

    data = None
    for selector in selectors:
        if type(selector) in [list, tuple]:
            data = selector[1]
            selector = selector[0]
        else:
            data = None

        tag = soup.select(selector)
        if tag and len(tag) > 0:
            if "debug" in kwargs:
                sys.stderr.write(str(selector) + "\n")
            break
        else:
            tag = None

    if data:
        return (tag, data)

    return tag


def get_title(myjson, soup):
    if myjson["author"] == "topstarnews":
        og_title = soup.find("meta", attrs={"itemprop": "name"})
        if og_title:
            return strify(html.unescape(strify(og_title["content"])))

    if ((myjson["author"] in [
            "ettoday",
            "koreastardaily",
            "chosun",
            "hotkorea",
            "donga"
    ]) or (
        "sbscnbc.sbs.co.kr" in myjson["url"]
    )):
        title = get_selector(soup, [
            ".block_title",  # ettoday
            "#content-title > h1",  # koreastardaily
            ".title_author_2011 #title_text",  # chosun
            ".atend_top .atend_title",  # sbscnbc
            ".xpress-post-title > h1",  # hotkorea
            ".article_tit > h3",  # sports donga
        ])
        if title and len(title) > 0:
            return strify(title[0].text)

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title:
        return strify(html.unescape(strify(og_title["content"])))
    elif "search" in myjson["url"]:
        return "(search)"


def get_author(url):
    if "naver." in url:
        return "naver"
    if ".joins.com" in url:
        return "joins"
    if "news1.kr/" in url:
        return "news1"
    if "topstarnews.net" in url:
        return "topstarnews"
    if "star.mt.co.kr" in url:
        return "starnews"
    if "osen.mt.co.kr" in url:
        return "osen"
    if "stardailynews.co.kr" in url:
        return "stardailynews"
    if "tvdaily.asiae.co.kr" in url:
        return "tvdaily"
    if "hankyung.com" in url:
        return "hankyung"
    if "liveen.co.kr" in url:
        return "liveen"
    if ".chosun.com" in url:
        return "chosun"
    if "mydaily.co.kr" in url:
        return "mydaily"
    if "mbn.co.kr" in url:
        return "mbn"
    if "chicnews.mk.co.kr" in url:
        return "chicnews"
    if "newsen.com" in url:
        return "newsen"
    if "hankooki.com" in url:
        return "hankooki"
    if "ettoday.net" in url:
        return "ettoday"
    if "koreastardaily.com" in url:
        return "koreastardaily"
    if "segye.com" in url:
        return "segye"
    if "xportsnews.com" in url:
        return "xportsnews"
    if "sbs.co.kr" in url:
        return "sbs"
    if "munhwanews.com" in url:
        return "munhwanews"
    if "pop.heraldcorp.com" in url:
        return "heraldpop"
    if "inews24.com" in url:
        return "inews24"
    if "fnnews.com" in url:
        return "fnnews"
    if "spotvnews.co.kr" in url:
        return "spotvnews"
    if "mk.co.kr" in url:
        return "mk"
    if "yonhapnews.co.kr" in url:
        return "yonhap"
    if "breaknews.com" in url:
        return "breaknews"
    if "getnews.co.kr" in url:
        return "getnews"
    if "hot-korea.net" in url:
        return "hotkorea"
    if "dispatch.co.kr" in url:
        return "dispatch"
    if ".donga.com" in url:
        return "donga"
    if ".ilyoseoul.co.kr" in url:
        return "ilyoseoul"
    if ".zenithnews.com" in url:
        return "zenithnews"
    if "saostar.vn" in url:
        return "saostar"
    if "khan.co.kr" in url:
        return "khan"
    if "gamechosun.co.kr" in url:
        return "gamechosun"
    if "www.ohmynews.com" in url:
        return "ohmynews"
    return None


def ascii_only(string):
    return ''.join([i if ord(i) < 128 else ' ' for i in string])


def parse_date(date, *args, **kwargs):
    if type(date) in [int, float]:
        return rssit.util.localize_datetime(datetime.datetime.utcfromtimestamp(date))
    #print(date)
    date = date.replace("&nbsp", " ")
    date = date.strip()
    # khan
    if date[0] == "(" and date[-1] == ")":
        date = date[1:-1]
        date = date.strip()
    date = re.sub("^([0-9][0-9][0-9][0-9])\. ([0-9][0-9])\.([0-9][0-9])[(].[)]", "\\1-\\2-\\3 ", date) # tvdaily
    date = re.sub("오후 *([0-9]*:[0-9]*)", "\\1PM", date)
    date = re.sub("(^|[^0-9])([0-9][0-9])\.([0-9][0-9])\.([0-9][0-9])  *([0-9][0-9]:[0-9][0-9])",
                  "\\1 20\\2-\\3-\\4 \\5", date) # mbn
    date = date.replace("\n", "   ")  # fnnews
    if "수정시간" in date:
        date = re.sub(".*수정시간", "", date)
    if "수정 :" in date:
        date = re.sub(".*수정 :", "", date)
    if "기사수정" in date: # xportsnews
        date = re.sub(".*기사수정", "", date)
    date = re.sub(" 송고.*", "", date) # news1
    date = re.sub("[(]월[)]", "", date) # chicnews
    date = re.sub("SBS *[A-Z]*", "", date) # sbs
    date = date.replace("mk Sports", "") # mk
    date = date.replace("더 맥트", "") # mk
    date = re.sub("投稿者.*", "", date) # hotkorea
    #print(date)
    #date = re.sub("입력: *(.*?) *\| *수정.*", "\\1", date) # chosun
    #print(date)
    date = re.sub(r"([0-9]*)년 *([0-9]*)월 *([0-9]*)일 *([0-9]*):([0-9]*)[PA]M", "\\1-\\2-\\3 \\4:\\5", date)  # inews24
    date = re.sub(r"([0-9]*)년 *([0-9]*)월 *([0-9]*)일", "\\1-\\2-\\3", date) # mk
    date = date.replace("년", "-")
    date = date.replace("年", "-")
    date = date.replace("월", "-")
    date = date.replace("月", "-")
    date = date.replace("日", "")
    date = date.replace("시", ":")
    date = ascii_only(date)
    date = re.sub("\( *\)", "", date)
    date = re.sub("\( *= *1 *\)", "", date) # workaround for news1
    date = re.sub("\( *= *1Biz *\)", "", date) # workaround for news1
    date = re.sub("\|", " ", date)
    date = re.sub(":[^0-9]*$", "", date)
    while re.search("^[^0-9]*[:.].*", date):
        date = re.sub("^[^0-9]*[:.]", "", date)
    date = date.strip()
    date = re.sub("^([0-9][0-9][0-9][0-9])\. ([0-9][0-9])\.([0-9][0-9])$", "\\1-\\2-\\3", date) #tvdaily
    #print(date)
    #print(parse(date))
    #print("")
    if not date:
        return None
    if "tz" in kwargs and kwargs["tz"]:
        return rssit.util.good_timezone_converter(parse(date), kwargs["tz"])
    else:
        return rssit.util.localize_datetime(parse(date))


def parse_date_tz(myjson, soup, newdate):
    if (myjson["author"] == "mydaily" or
        myjson["author"] == "xportsnews"):
        return parse_date(newdate, tz="Etc/GMT-9")
    else:
        return parse_date(newdate)


def get_date(myjson, soup):
    if myjson["author"] in [
            "ettoday"
            ]:
        return parse_date(-1)

    if myjson["author"] in ["topstarnews"]:
        datetag = soup.select("meta[name='sailthru.date']")
        if datetag:
            return parse_date_tz(myjson, soup, datetag[0]["content"])

    if "sbs.co.kr" in myjson["url"]:
        datetag = soup.select(".date > meta[itemprop='datePublished']")
        if datetag:
            return parse_date_tz(myjson, soup, datetag[0]["content"])

    # not khan.co.kr, it has 1999-11-30 as the date
    if "star.fnnews.com" in myjson["url"] or myjson["author"] in [
            "breaknews",
            "getnews",
            "hotkorea",
            "dispatch",
            "ilyoseoul",
            "zenithnews",
            "saostar",
            "gamechosun"
    ]:
        datetag = soup.select("meta[property='article:published_time']")
        if datetag:
            return parse_date_tz(myjson, soup, datetag[0]["content"])

    if "m.post.naver.com" in myjson["url"]:
        datetag = soup.select("meta[property='nv:news:date']")
        if datetag:
            return parse_date_tz(myjson, soup, datetag[0]["content"])

    if myjson["author"] == "mydaily":
        newsid = re.sub(".*newsid=([0-9]*).*", "\\1", myjson["url"])
        newdate = newsid[0:4] + "-" + newsid[4:6] + "-" + newsid[6:8] + " " + newsid[8:10] + ":" + newsid[10:12]
        return parse_date_tz(myjson, soup, newdate)

    datetag = get_selector(soup, [
        ".article_info .author em",
        ".article_tit .write_info .write",
        "#article_body_content .title .info",  # news1
        "font.read_time",  # chicnews
        ".gisacopyright",
        "#content-title > h2",  # koreastardaily
        #".read_view_wrap .read_view_date",  # mydaily
        ".date_ctrl_2011 #date_text",  # chosun
        "#_article font.read_time",  # tvdaily
        ".article_head > .clearfx > .data",  # segye
        "#articleSubecjt .newsInfo",  # xportsnews
        "em.sedafs_date",  # sbs program
        "#content > .wrap_tit > p.date",  # sbsfune
        ".atend_top .atend_reporter",  # sbs cnbc
        "td > .View_Time",  # munhwanews
        "#content > .article > .info > .info_left",  # heraldpop
        ".container #LeftMenuArea #content .info > span",  # inews24 (joynews)
        ".content > .article_head > .byline",  # www.fnnews.com
        ".arl_view_writer > .arl_view_date",  # spotvnews
        ".news_title_author > ul > li.lasttime",  # mk
        "#main-content .gn_rsmall",  # hotkorea
        ".xpress-post-footer",  # hotkorea
        ".article_tit > p",  # sports donga
        "article.wrap_news_body > div.byline > em",  # khan
        "#container > div.art_header > div.function_wrap >  div.pagecontrol > div.byline > em"  # khan images
    ])

    if not datetag:
        sys.stderr.write("no date tag found\n")
        return

    date = None
    for date_tag in datetag:
        try:
            if myjson["author"] == "koreastardaily":
                date = parse_date_tz(myjson, soup, strify(date_tag.contents[0]))
            else:
                date = parse_date_tz(myjson, soup, strify(date_tag.text))
        except:
            if date:
                sys.stderr.write("error parsing date (but already found ok date)\n")
            else:
                sys.stderr.write("error parsing date\n")
        ##if myjson["author"] == "naver":
        ##    if not "오후" in date_tag.text:
        ##        continue
        ##    date = parse(date_tag.text.replace("오후", ""))
        ##else:
        ##    date = parse_date(date_tag.text)

    return date


def is_album(myjson, soup):
    return (
        (myjson["author"] == "hankooki" and "mm_view.php" in myjson["url"]) or
        (myjson["author"] == "sbs" and "program.sbs.co.kr" in myjson["url"]) or
        (myjson["author"] == "hotkorea" and "/photobook/" in myjson["url"])
    )


def end_getimages(myjson, soup, oldimages):
    images = []
    for imagesrc in oldimages:
        image_full_url = urllib.parse.urljoin(myjson["url"], imagesrc)
        max_quality = get_max_quality(image_full_url)
        if max_quality:
            images.append(strify(max_quality))

    return images


def get_soup_body(myjson, soup):
    if "m.post.naver.com" in myjson["url"]:
        return bs4.BeautifulSoup(str(soup.select("script[type='x-clip-content']")[0].text), 'lxml')
    return soup


def get_images(myjson, soup):
    if myjson["author"] == "hankooki" and "mm_view.php" in myjson["url"]:
        jsondatare = re.search(r"var *arrView *= *(?P<json>.*?) *;\n", str(soup))
        if not jsondatare:
            sys.stderr.write("No json data!\n")
            return None
        jsondata = str(jsondatare.group("json"))
        decoded = demjson.decode(jsondata)
        images = []
        for img in decoded:
            max_quality = get_max_quality(img["photo"])
            if max_quality:
                images.append(strify(max_quality))
        return images

    if myjson["author"] == "chosun" and "html_dir" in myjson["url"]:
        jsondatare = re.findall(r"_photoTable._photoIdx[+][+]. *= *new *Array *[(]\"([^\"]*)\"", str(soup))
        if jsondatare:
            return end_getimages(myjson, soup, jsondatare)

    soup = get_soup_body(myjson, soup)

    imagestag = get_selector(soup, [
        "#adiContents img",
        "#article_body_content div[itemprop='articleBody'] td > img",  # news1
        ".article .img_pop_div > img", # chosun
        "#content .news_article #viewFrm .news_photo center > img", # segye
        ".articletext img",  # heraldpop
        ".post-content-right > .post-content > div[align='center'] a > img.aligncenter",  # fnnews
        "#arl_view_content > div[itemprop='articleBody'] .news_photo_table td > img",  # spotvnews
        ".article_outer .main_image p > img, .article_outer .post_body p img",  # dispatch
        #".post_body strong > img, .main_image img"  # dispatch
        "#article div[align='center'] > img",  # mydaily
        ".article_word > .articlePhoto img",  # donga
        "a.se_mediaArea > img.se_mediaImage",  # naver mobile post
        ".article img",
        "#article img",
        ".articletext img",
        "#_article table[align='center'] img",
        "#_article img.view_photo",
        "#_article .article_photo img",
        "#articleBody img",
        "#articleBody .iframe_img img:nth-of-type(2)",
        "#newsContent .iframe_img img:nth-of-type(2)",
        "#articeBody .img_frame img",
        "#textBody img",
        "#news_contents img",
        "#arl_view_content img",
        ".articleImg img",
        "#newsViewArea img",
        "#articleContent img",
        "#articleContent #img img",
        "#newsContent img.article-photo-mtn",
        "#article_content img",
        "#article_body .img_center > img",  # mk
        "div[itemprop='articleBody'] img",
        "div[itemprop='articleBody'] img.news1_photo",
        "div[itemprop='articleBody'] div[rel='prettyPhoto'] img",
        "div[itemprop='articleBody'] .centerimg img",
        "div[itemprop='articleBody'] .center_image img",
        ".center_image > img",
        ".article_view img",
        "img#newsimg",
        ".article_photo img",
        ".articlePhoto img",
        "#__newsBody__ .he22 td > img",
        ".article_image > img",
        "#CmAdContent img",
        #".article_outer .main_image p > img, .article_outer .post_body p img",
        ".article-img img",
        ".portlet .thumbnail img",
        "#news_textArea img",
        ".news_imgbox img",
        ".view_txt img",
        "#IDContents img",
        "#view_con img",
        "#newsEndContents img",
        ".articleBox img",
        ".rns_text img",
        "#article_txt img",
        "#ndArtBody .imgframe img",
        ".view_box center img",
        ".newsbm_img_wrap > img",
        ".article .detail img",
        "#articeBody img",
        "center table td a > img",  # topstarnews search
        ".gisaimg > ul > li > img",  # hankooki
        ".part_thumb_2 .box_0 .pic img",  # star.ettoday.net
        "#content-body p > img",  # koreastardaily
        "#adnmore_inImage div[align='center'] > table > tr > td > a > img",  # topstarnews article
        ".sprg_main_w #post_cont_wrap p > img",  # sbs program
        "#content > #etv_news_content img[alt='이미지']",  # sbsfune
        "#content .atend_center img[alt='이미지']",  # sbscnbc
        ".ngg-gallery-thumbnail > a > img",  # hotkorea photobook
        ".gn_file > a > img",  # hotkorea
        ".xpress-post-entry .main-text p > a > img.aligncenter",  # hotkorea
        ".article_photo_center > #mltPhoto > img"  # khan images
    ])

    if myjson["author"] == "donga":
        imagestag = soup.select(".article_word > .articlePhoto img")

    if not imagestag:
        return

    images = []
    for image in imagestag:
        imagesrc = image["src"]
        if image.has_attr("data-src"):
            imagesrc = image["data-src"]
        image_full_url = urllib.parse.urljoin(myjson["url"], imagesrc)
        max_quality = get_max_quality(image_full_url)
        if max_quality:
            images.append(strify(max_quality))

    return images


def get_description(myjson, soup):
    desc_tag = get_selector(soup, [
        "#article_content #adiContents",
        "#article_body_content .detail",
        "#CmAdContent",  # chicnews, heraldpop
        "#GS_Content",  # hankooki
        "#wrap #read_left #article",  # mydaily
        ".photo_art_box",  # chosun
        "#article_2011",  # chosun
        "#_article .read",  # tvdaily
        "#viewFrm #article_txt",  # segye
        "#CmAdContent .newsView div[itemprop='articleBody']",  # xportsnews
        ".sprg_main_w #post_cont_wrap",  # sbs
        "#content > #etv_news_content",  # sbsfune
        ".w_article_left > .article_cont_area",  # sbs news
        "#content .atend_center",  # sbs cnbc
        "#articleBody #talklink_contents",  # munhwanews
        "#news_content > div[itemprop='articleBody']",  # inews24
        ".post-container .post-content-right .post-content.description",  # star.fnnews.com
        ".article_wrap > .article_body > #article_content",  # www.fnnews.com
        "#arl_view_content",  # spotvnews
        "#article_body",  # mk
        "#CLtag",  # breaknews
        ".detailWrap > .detailCont",  # getnews
        ".xpress-post-entry",  # hotkorea photobook
        "#center_contents > #main-content",  # hotkorea
        ".post_body",  # dispatch
        ".article_cont #articleBody",  # sports donga
        ".se_component_wrap.sect_dsc",  # naver mobile post
        ".page-wrap > main article #content_detail",  # saostar
        "article.wrap_news_body > div.desc_body",  # khan
        ".art_cont > .art_body p.content_text",  # khan images
        ".cnt_article_wrap .cnt_lef_area div[itemprop='articleBody']"  # gamechosun
    ])

    if not desc_tag:
        return

    #return "\n".join(list(desc_tag[0].strings))
    desc = strify(desc_tag[0])

    if myjson["author"] == "hotkorea":
        desc = re.sub(r"</a>[)] [[] [0-9]*hit []]", "</a>)", desc)  # not regular spaces!

    return strify(desc)


def get_nextpage(myjson, soup):
    if myjson["author"] == "hotkorea" and "photobook" in myjson["url"]:
        tag = get_selector(soup, [
            ".ngg-navigation > .next"
        ])

        if not tag:
            return

        return strify(tag[0]["href"])

    return


def clean_url(url):
    return strify(url).replace("\n", "").replace("\r", "").replace("\t", "")


def get_article_url(url):
    return strify(url)


def get_segye_photos(myjson, soup):
    strsoup = str(soup)
    match = re.search(r"var *photoData *= *eval *\( *' *(\[.*?\]) *' *\) *;", strsoup)
    if not match or not match.group(1):
        return

    jsondatastr = match.group(1)
    jsondata = demjson.decode(jsondatastr)
    print(jsondata)


def get_yonhap_photos(config, myjson, soup):
    newquery = re.sub(r".*query=([^&]*).*", "\\1", myjson["url"])
    if not newquery or newquery == myjson["url"]:
        return

    firsturl = 'http://srch.yonhapnews.co.kr/NewSearch.aspx?callback=Search.SearchPreCallback&query='
    lasturl = '&ctype=P&page_size=16&channel=basic_kr'

    url = firsturl + newquery + lasturl

    if "page_no" in config:
        url += "&page_no=" + str(config["page_no"])

    config["httpheader_Referer"] = myjson["url"]
    data = rssit.util.download(url, config=config)
    data = re.sub(r"^Search.SearchPreCallback\(", "", data)
    data = data.strip()
    data = re.sub(r"\);$", "", data)
    jsondata = demjson.decode(data)

    myjson = {
        "title": myjson["author"],
        "author": myjson["author"],
        "url": myjson["url"],
        "config": {
            "generator": "news"
        },
        "entries": []
    }

    articles = []

    for photo in jsondata["KQ_PHOTO"]["result"]:
        articles.append({
            "url": "http://www.yonhapnews.co.kr/photos/1990000000.html?cid=" + photo["CONTENTS_ID"],
            "caption": photo["TITLE"].replace("<b>", "").replace("</b>", ""),
            "aid": photo["CONTENTS_ID"][5:15],
            "date": parse_date(photo["DIST_DATE"][0:4] + "-" + photo["DIST_DATE"][4:6] + "-" + photo["DIST_DATE"][6:8] +
                          " " + photo["DIST_TIME"][0:2] + ":" + photo["DIST_TIME"][2:4]),
            "images": [get_max_quality("http://img.yonhapnews.co.kr/" + photo["THUMBNAIL_FILE_PATH"] + "/" + photo["THUMBNAIL_FILE_NAME"])],
            "videos": []
        })

    if not myjson["url"] or len(articles) == 0:
        return

    for entry_i in range(len(articles)):
        articles[entry_i] = fix_entry(articles[entry_i])
        articles[entry_i]["author"] = myjson["author"]

    #print(len(articles))
    #pprint.pprint(articles)

    #return do_article_list(config, articles, myjson)
    return articles


def do_api(config, path):
    author = str(re.sub(r".*?/api/([^/]*).*", "\\1", path))

    if re.match(r".*?/api/[^/]*/([^/?]+)", path):
        query = re.sub(r".*?/api/[^/]*/([^/?]+)", "\\1", path)
    else:
        query = None

    myjson = {
        "title": author,
        "author": author,
        "url": None,
        "config": {
            "generator": "news"
        },
        "entries": []
    }

    articles = []
    if author == "joins":
        url = 'http://searchapi.joins.com/search_jsonp.jsp?query=' + query
        if "collection" in config and config["collection"]:
            url += "&collection=" + config["collection"]
        url += "&sfield=ART_TITLE"
        if "startCount" in config and config["startCount"]:
            url += "&startCount=" + str(config["startCount"])
        url += "&callback=?"
        url = rssit.util.quote_url1(url)
        myjson["url"] = url
        data = rssit.util.download(url)
        data = re.sub(r"^[?][(](.*)[)];$", "\\1", data)
        jsondata = demjson.decode(data)
        collections = jsondata["SearchQueryResult"]["Collection"]

        def remove_tags(text):
            return text.replace("<!HS>", "").replace("<!HE>", "")

        for collection in collections:
            documentset = collection["DocumentSet"]
            if documentset["Count"] == 0:
                continue

            documents = documentset["Document"]
            for document in documents:
                field = document["Field"]
                thumb_url = urllib.parse.urljoin("http://pds.joins.com/", field["ART_THUMB"])
                thumb_url = get_max_quality(thumb_url)
                fday = field['SERVICE_DAY']
                syear = int(fday[0:4])
                smonth = int(fday[4:6])
                sday = int(fday[6:8])
                date = datetime.datetime(year=syear, month=smonth, day=sday).timestamp()
                date += int(field['SERVICE_TIME'])
                date = parse_date(date)
                eurl = "http://isplus.live.joins.com/news/article/article.asp?total_id="
                eurl += field["DOCID"]
                articles.append({
                    "url": strify(eurl),
                    "caption": strify(remove_tags(field["ART_TITLE"])),
                    "aid": strify(field["DOCID"]),
                    "date": date,
                    "description": strify(remove_tags(field["ART_CONTENT"])),
                    "images": [strify(thumb_url)],
                    "videos": []
                })
    elif author == "ohmynews":
        if "keyword" in config and config["keyword"]:
            query = config["keyword"]
        url = "http://www.ohmynews.com/NWS_Web/Search/neo_json.aspx?keyword=" + query
        post = ""
        if "page" in config and config["page"]:
            url += "&page=" + str(config["page"])
        if "order" in config and config["order"]:
            url += "&order=" + strify(config["order"])

        if "list_cnt" in config and config["list_cnt"]:
            post += "list_cnt=" + str(config["list_cnt"])
        else:
            post += "list_cnt=20"
        if "article_type" in config and config["article_type"]:
            post += "&article_type=" + strify(config["article_type"])
        else:
            post += "&article_type=IE"

        if "article_type=IE" in post:
            config["quick"] = True

        #url = rssit.util.quote_url1(url)
        myjson["url"] = url
        data = rssit.util.download(url, post=post.encode("utf-8"), config=config)
        data = demjson.decode(data)
        data = demjson.decode(data["data"][0])
        for item in data["data"]:
            date = datetime.datetime.fromtimestamp(int(item["datei"]) / 1000)
            articles.append({
                "url": strify(item["url"]),
                "caption": strify(item["desc"]),
                "aid": strify(item["docid"]),
                "date": date,
                "images": [get_max_quality(strify(item["thumbnail"]))],
                "videos": []
            })

    if not myjson["url"] or len(articles) == 0:
        return

    for entry_i in range(len(articles)):
        articles[entry_i] = fix_entry(articles[entry_i])
        articles[entry_i]["author"] = author

    return do_article_list(config, articles, myjson)


def fix_entry(entry):
    realcaption = None
    caption = None
    aid = ""
    if "aid" in entry and entry["aid"]:
        aid = entry["aid"] + " "
    if "caption" in entry and entry["caption"]:
        realcaption = strify(entry["caption"].strip())
        caption = strify(aid + realcaption)
    entry["media_caption"] = caption
    entry["caption"] = realcaption
    entry["similarcaption"] = realcaption
    return entry


def get_articles(config, myjson, soup):
    if myjson["author"] == "joins":
        if "isplusSearch" not in myjson["url"]:
            return
    elif myjson["author"] in ["news1", "topstarnews", "hankooki", "heraldpop", "inews24", "mk", "getnews", "dispatch"]:
        if "search.php" not in myjson["url"]:
            return
    elif myjson["author"] in ["starnews", "osen", "mydaily", "mbn", "fnnews"]:
        if "search" not in myjson["url"]:
            return
    elif myjson["author"] in ["sbs", "hotkorea"]:
        if "/search/" not in myjson["url"]:
            return
    elif myjson["author"] == "tvdaily" or myjson["author"] == "chicnews":
        if "searchs.php" not in myjson["url"]:
            return
    elif myjson["author"] == "hankyung":
        if "search.hankyung.com" not in myjson["url"]:
            return
    elif myjson["author"] == "chosun":
        if "search.chosun.com" not in myjson["url"]:
            return
    elif myjson["author"] == "newsen":
        if "news_list.php" not in myjson["url"]:
            return
    elif myjson["author"] == "segye":
        if not re.search("search[^./]*\.segye\.com", myjson["url"]):
            if "photoView" in myjson["url"] and False:
                return get_segye_photos(myjson, soup)
            else:
                return
    elif myjson["author"] == "xportsnews":
        if "ac=article_search" not in myjson["url"]:
            return
    elif myjson["author"] == "spotvnews":
        if "act=articleList" not in myjson["url"]:
            return
    elif myjson["author"] == "yonhap":
        if not re.search(r"[?&]query=", myjson["url"]):
            return
        return get_yonhap_photos(config, myjson, soup)
    elif myjson["author"] in ["breaknews", "khan"]:
        if "search.html" not in myjson["url"]:
            return
    elif myjson["author"] == "donga":
        if "/Search" not in myjson["url"]:
            return
    elif myjson["author"] == "saostar":
        if "/?s=" not in myjson["url"]:
            return
    elif myjson["author"] == "ohmynews":
        if "/Search/" not in myjson["url"]:
            return
    else:
        if "news/articleList" not in myjson["url"]:
            return

    articles = []

    parent_selectors = [
        # joins
        {
            "parent": "#news_list .bd ul li dl",
            "link": "dt a",
            "caption": "dt a",
            "date": "dt .date",
            "images": ".photo img",
            "description": "dd.s_read_cr"
        },
        {
            "parent": "#search_contents .bd ul li dl",
            "link": "dt a",
            "caption": "dt a",
            "date": ".date",
            "images": ".photo img"
        },
        # news1 photo
        {
            "parent": ".search_detail .listType3 ul li",
            "link": "a",
            "caption": "a > strong",
            "date": "span.date",
            "images": ".thumb img",
            "aid": lambda soup: re.sub(r".*/\?([0-9]*).*", "\\1", soup.select("a")[0]["href"])
        },
        # news1 list
        {
            "parent": ".search_detail .listType1 ul li",
            "link": "a",
            "caption": ".info a",
            "date": "dd.date",
            "images": ".thumb img",
            "aid": lambda soup: re.sub(r".*/\?([0-9]*).*", "\\1", soup.select("a")[0]["href"])
        },
        # topstarnews
        {
            "parent": "table#search_part_1 > tr > td > table > tr > td",
            "link": "center > table > tr > td > a",
            "caption": "center > table > tr > td > span > a",
            "date": ".street-photo2",
            "images": "center > table > tr > td > a > img",
            "aid": lambda soup: re.sub(r".*[^a-zA-Z0-9_]number=([0-9]*).*", "\\1", soup.select("center > table > tr > td > a")[0]["href"])
        },
        # starnews
        {
            "parent": "#container > #content > .fbox li.bundle",
            "link": ".txt > a",
            "caption": ".txt > a",
            "date": "-1",
            "images": ".thum img",
            "aid": lambda soup: re.sub(r".*[^a-zA-Z0-9_]no=([0-9]*).*", "\\1", soup.select(".txt > a")[0]["href"])
        },
        # osen
        {
            "parent": "#container .searchBox > table tr > td",
            "link": "a",
            "caption": "p.photoView",
            "date": "-1",
            "images": "a > img",
            "aid": lambda soup: re.sub(r".*/([0-9A-Za-z]*)", "\\1", soup.select("a")[0]["href"])
        },
        # liveen, ilyoseoul
        {
            "parent": "table#article-list > tr > td > table > tr > td > table",
            "link": "td.list-titles a",
            "caption": "td.list-titles a",
            "description": "td.list-summary a",
            "date": "td.list-times",
            "images": ".list-photos img, a > img.border-box",
            "html": True,
            "aid": lambda soup: re.sub(r".*idxno=([0-9]*).*", "\\1", str(soup.select("td.list-titles a")[0]["href"]))
        },
        # stardailynews
        {
            "parent": "#ND_Warp table tr > td table tr > td table tr > td table",
            "parent_valid": lambda parent, myjson, soup: myjson["author"] == "stardailynews",
            "link": "tr > td > span > a",
            "caption": "tr > td > span > a",
            "description": "tr > td > p",
            "date": "-1",
            "images": "tr > td img",
            "html": True,
            "aid": lambda soup: re.sub(r".*idxno=([0-9]*).*", "\\1", str(soup.select("tr > td > span > a")[0]["href"]))
        },
        # newsen
        {
            "parent": "table[align='left'] > tr > td[align='left'] > table[align='center'] > tr[bgcolor]",
            "link": "a.line",
            "caption": "a > b",
            "description": "td[colspan='2'] > a",
            "date": "td[nowrap]",
            "images": "a > img",
            "aid": lambda soup: re.sub(r".*uid=([^&]*).*", "\\1", str(soup.select("td > a")[0]["href"])),
            "html": True
        },
        # tvdaily
        {
            "parent": "body > table tr > td > table tr > td > table tr > td > table tr > td",
            "parent_valid": lambda parent, myjson, soup: myjson["author"] == "tvdaily",
            "link": "a.sublist",
            "date": "span.date",
            "caption": "a.sublist",
            "description": "p",
            "images": "a > img",
            "imagedata": lambda entry, soup: {
                "date": re.sub(r"[^0-9]*", "", str(soup.select("span.date")[0].text)),
                "aid": re.sub(r".*aid=([^&]*).*", "\\1", str(soup.select("a.sublist")[0]["href"]))
            },
            "aid": lambda soup: re.sub(r".*aid=([^&]*).*", "\\1", str(soup.select("a.sublist")[0]["href"])),
            "html": True
        },
        # hankyung
        {
            "parent": ".hk_news .section_cont > ul.article > li",
            "link": ".txt_wrap > a",
            "caption": ".txt_wrap .tit",
            "description": ".txt_wrap > p.txt",
            "date": ".info span.date_time",
            "images": ".thumbnail img",
            "html": True
        },
        # old chosun
        {
            "parent": ".result_box > section.result > dl",
            "link": "dt > a",
            "caption": "dt > a",
            "description": "dd > a",
            "date": "dt > em",
            "images": ".thumb img",
            "aid": lambda soup: re.sub(r".*/([^/.?&]*).html$", "\\1", str(soup.select("dt > a")[0]["href"])),
            "html": True
        },
        # new chosun
        {
            "parent": ".schCont_in .search_news_box .search_news",
            "link": "dt > a",
            "caption": "dt > a",
            "description": ".desc",
            "date": ".date",
            "images": ".thumb img",
            "aid": lambda soup: re.sub(r".*/([^/.?&]*).html$", "\\1", str(soup.select("dt > a")[0]["href"])),
            "html": True
        },
        # mydaily
        {
            "parent": "#wrap > #section_left > .section_list",
            "link": ".section_list_text > dt > a",
            "caption": ".section_list_text > dt > a",
            "description": ".section_list_text > dd",
            "date": ".section_list_text > dd > p",
            "images": ".section_list_img > a > img",
            "aid": lambda soup: re.sub(r".*newsid=([^&]*).*", "\\1", str(soup.select(".section_list_text > dt > a")[0]["href"])),
            "html": True
        },
        # mbn
        {
            "parent": "#search_result > .collaction_news > ul > li",
            "link": "a",
            "caption": "a > strong",
            "description": "p.desc",
            "date": ".write_time",
            "images": ".thumb img",
            "aid": lambda soup: re.sub(r".*news_seq_no=([^&]*).*", "\\1", str(soup.select("a")[0]["href"])),
            "html": True
        },
        # chicnews
        {
            "parent": "#container .container_left dl.article",
            "link": ".tit > a",
            "caption": ".tit > a",
            "description": ".subtxt",
            "date": "span.date",
            "images": ".img img",
            "imagedata": lambda entry, soup: {
                "date": re.sub(r"[^0-9]*", "", str(soup.select("span.date")[0].text)),
                "aid": re.sub(r".*aid=([^&]*).*", "\\1", str(soup.select(".tit > a")[0]["href"]))
            },
            "aid": lambda soup: re.sub(r".*aid=([^&]*).*", "\\1", str(soup.select(".tit > a")[0]["href"])),
            "html": True
        },
        # hankooki
        {
            "parent": "#SectionCenter .news > .pb12",
            "link": "li.title > a",
            "caption": "li.title > a",
            "description": "li.con > a",
            "date": "li.source",
            "images": ".thumb > a > img",
            "aid": lambda soup: re.sub(r".*/[a-zA-Z]*([^/]*)\.htm[^/]*$", "\\1", str(soup.select("li.title > a")[0]["href"])),
            "html": True,
            "is_valid": lambda soup: soup.select("li.title > a")[0]["href"].strip()
        },
        # hankooki images
        {
            "parent": "#SectionCenter .images > .pr20",
            "link": ".txt > a",
            "caption": ".txt > a",
            "date": "-1",
            "images": ".pic img"
        },
        # segye (doesn't work, needs api call with access token)
        {
            "parent": "#articleArea .area_box",
            "link": ".r_txt .title_cr > a",
            "caption": ".r_txt .title_cr > a",
            "description": ".read_cr > a",
            "date": "span.date",
            "images": ".Pho .photo img",
            "aid": lambda soup: re.sub(r".*/[0-9]*\.htm[^/]*$", "\\1", soup.select(".r_txt .title_cr > a")[0]["href"]),
            "html": True
        },
        # xportsnews
        {
            "parent": "#list_common_wrap > ul.list_news > li",
            "link": "dl.dlist > dt > a",
            "caption": "dl.dlist > dt > a",
            "description": "dl.dlist > dd:nth-of-type(1)",
            "date": "dl.dlist > dd:nth-of-type(2) > span.data",
            "images": ".thumb > a > img",
            "aid": lambda soup: re.sub(r".*entry_id=([0-9]*).*", "\\1", soup.select("dl.dlist > dt > a")[0]["href"]),
            "html": True
        },
        # sbs
        {
            "parent": ".pss_content_w .pssc_inner ul.ps_newslist > li div.psil_inner",
            "link": "a.psil_link",
            "caption": "strong.psil_tit",
            "description": "p.psil_txt",
            "date": "span.psil_info",
            "images": "span.psil_img > img",
            "html": True
        },
        # munhwanews
        {
            "parent": "#ND_Warp > table > tr > td > table > tr > td > table > tr",
            "parent_valid": lambda parent, myjson, soup: myjson["author"] == "munhwanews",
            "link": ".ArtList_Title > a",
            "caption": ".ArtList_Title > a",
            "description": ".ArtList_Title > div:nth-of-type(1)",
            "date": ".ArtList_Title > div > font.FontEng",
            "images": "td > img",
            "aid": lambda soup: re.sub(r".*idxno=([0-9]*).*", "\\1", soup.select(".ArtList_Title > a")[0]["href"]),
            "html": True
        },
        # heraldpop
        {
            "parent": "#wrap > #container > #content > .slist > dl",
            "parent_valid": lambda parent, myjson, soup: myjson["author"] == "heraldpop",
            "link": "dd > a",
            "caption": "dd > a > h2",
            "description": "dd > a > p",
            "date": "dd > span",
            "images": "dt > a > img",
            "aid": lambda soup: re.sub(r".*ud=([0-9]*).*", "\\1", soup.select("dd > a")[0]["href"])[8:],
            "html": True
        },
        # inews24
        {
            "parent": "center > #wrapper .list > .box2",
            "parent_valid": lambda parent, myjson, soup: myjson["author"] == "inews24",
            "link": ".news li.title > a",
            "caption": ".news li.title > a",
            "description": ".news > ul > li:nth-of-type(2) > a:nth-of-type(2)",
            "date": ".end > .time",
            "images": ".thumb > a > img",
            "aid": lambda soup: re.sub(r".*g_serial=([0-9]*).*", "\\1", soup.select(".news li.title > a")[0]["href"]),
            "html": True
        },
        # fnnews
        {
            "parent": "#container > .content > .section_list_wrap > .section_list > .bd > ul > li",
            "link": "strong > a",
            "caption": "strong > a",
            "description": ".cont_txt > a",
            "date": ".byline > em:nth-of-type(2)",
            "images": ".thumb_img > img",
            "aid": lambda soup: re.sub(r".*/([0-9]*)[^/]*", "\\1", soup.select("strong > a")[0]["href"])[8:],
            "html": True
        },
        # spotvnews
        {
            "parent": "#content > .article_list > table tr",
            "parent_valid": lambda parent, myjson, soup: myjson["author"] == "spotvnews",
            "link": "td:nth-of-type(1) > a",
            "caption": "td:nth-of-type(1) > a",
            "date": "td:nth-of-type(2)",
            "aid": lambda soup: re.sub(r".*idxno=([0-9]*).*", "\\1", soup.select("td:nth-of-type(1) > a")[0]["href"]),
            "html": True
        },
        # mk
        {
            "parent": "td > div.sub_list",
            "parent_valid": lambda parent, myjson, soup: myjson["author"] == "mk",
            "link": ".art_tit > a",
            "caption": ".art_tit > a",
            "date": "/.art_time",
            "description": "/a",
            "aid": lambda soup: re.sub(r".*no=([0-9]*).*", "\\1", soup.select(".art_tit > a")[0]["href"]),
            "html": True
        },
        # yonhap
        {
            "parent": "#photo_list_2 .search_pho_list_list_c",
            "link": "div.txt > a",
            "caption": "div.txt > a",
            "date": "div.txt > p.pbdt_s",
            "aid": lambda soup: re.sub(r".*/[^/]*\.[^/]*", "\\1", soup.select("div.txt > a")[0]["href"])[5:15],
            "html": True
        },
        # breaknews
        {
            "parent": "#contents_wrap_sub > table:nth-of-type(3) > tr > td > table > tr:nth-of-type(2) > td > table:nth-of-type(2) > tr",
            "link": "td:nth-of-type(2) > a:nth-of-type(1)",
            "caption": "td:nth-of-type(2) > a:nth-of-type(1)",
            "date": "td.data",
            "aid": lambda soup: re.sub(r".*uid=([0-9]*).*", "\\1", soup.select("td:nth-of-type(2) > a:nth-of-type(1)")[0]["href"]),
            "html": True
        },
        # getnews
        {
            "parent": "ul#listAddID > li",
            "link": "/a",
            "caption": "strong.tit",
            "date": "-1",
            "description": "span.cont",
            "images": "img",
            "aid": lambda soup: re.sub(r".*ud=([0-9]*).*", "\\1", extra_select(soup, "/a")[0]["href"])[10:],
            "html": True
        },
        # hotkorea
        {
            "parent": "#main-content > div > div > strong",
            "parent_process": lambda myjson, soup: (
                "/xpress/" in extra_select(soup, "/a")[0]["href"] or
                "/gallery/" in extra_select(soup, "/a")[0]["href"] or
                "/photobook/" in extra_select(soup, "/a")[0]["href"]),
            "link": "/a",
            "caption": "/a",
            "date": "-1"
        },
        # dispatch
        {
            "parent": ".page_wrap > .contents_body_wrap > .row > a",
            "parent_valid": lambda parent, myjson, osup: myjson["author"] == "dispatch",
            "link": "/",
            "caption": "div > h6",
            "date": "-1",
            "description": "div > p",
            "images": lambda soup: re.sub(".*url\\((.*?)\\);.*", "\\1", extra_select(soup, ".img-back-center")[0]["style"]),
            "aid": lambda soup: re.sub(r".*/([0-9]*).*", "\\1", soup["href"]),
            "html": True
        },
        # sports donga
        {
            "parent": ".sub_contents > ul.list_news > li",
            "link": "dl > dt > a",
            "caption": "dl > dt > a",
            "date": "dd.date",
            "description": "dd.txt",
            "images": ".thum_img > a > img",
            "aid": lambda soup: re.sub(r".*/([0-9]*)/[0-9]$", "\\1", extra_select(soup, "dl > dt > a")[0]["href"]),
            "html": True
        },
        # zenithnews
        {
            "parent": "#ND_Warp > table > tr > td > table > tr > td > table > tr > td > table",
            "link": ".ArtList_Title > a",
            "caption": ".ArtList_Title",
            "date": "tr > td > table > tr > td > font.FontEng",
            "description": "tr > td > table > tr:nth-of-type(2) > td > a",
            "images": "tr > td > div > a > img",
            "aid": lambda soup: re.sub(r".*idxno=([0-9]*).*", "\\1", soup.select(".ArtList_Title > a")[0]["href"]),
            "html": True
        },
        # saostar
        {
            "parent": ".list_cat_news > .box_vertical.pkg",
            "link": ".info_vertical_news > h3 > a",
            "caption": ".info_vertical_news > h3 > a",
            "date": lambda soup: strify(extra_select(soup, "time.time-ago")[0]["datetime"]),
            "description": ".sapo_news",
            "images": ".module-thumb > a > img",
            "aid": lambda soup: re.sub(r".*-([0-9]*)\.html$", "\\1", soup.select(".info_vertical_news > h3 > a")[0]["href"]),
            "html": True
        },
        # khan.co.kr
        {
            "parent": "#wrap > #container > .content > .news.section > dl.phArtc",
            "link": "dt > a",
            "caption": "dt > a",
            "date": "dt span.date",
            "description": "dd.txt",
            "aid": lambda soup: re.sub(r".*art_id=([0-9]*).*", "\\1", soup.select("dt > a")[0]["href"]),
            "html": True
        },
        # khan.co.kr images
        {
            "parent": "#wrap > #container > .content > .pimage.section > ul.photolist > li",
            "link": "p > a",
            "caption": "p > a",
            "date": "-1",
            "images": "div.thumb img",
            "aid": lambda soup: re.sub(r".*artid=([0-9]*).*", "\\1", soup.select("p > a")[0]["href"]),
            "html": True
        },
        # ohmynews images (needs api, doesn't work)
        {
            "parent": ".section_sch > .cssPhotoList > .article > ul > li",
            "link": "/a",
            "caption": lambda soup: extra_select(soup, "/a")[0]["title"],
            "date": "-1",
            "images": "/a > img",
            "aid": lambda soup: re.sub(r".*CNTN_CD=([A-Z0-9]*).*", "\\1", extra_select(soup, "/a")[0]["href"]),
            "html": True
        }
    ]

    def extra_select(el, selector):
        root = False

        if type(selector) == type(lambda x: x):  # XXX ugly
            return [selector(el)]

        if selector == "/":
            return [el]

        if selector[0] == "/":
            root = True
            selector = selector[1:]

        selected = el.select(selector)
        if not root:
            return selected

        newselected = []
        for i in selected:
            if i.parent == el:
                newselected.append(i)
        return newselected

    parenttag = None
    for selector in parent_selectors:
        parenttag = soup.select(selector["parent"])
        if parenttag and len(parenttag) > 0:
            #print(selector)
            if "parent_valid" in selector:
                if selector["parent_valid"](parenttag, myjson, soup):
                    break
            else:
                break

        parenttag = None

    if not parenttag:
        return []

    for a in parenttag:
        if not extra_select(a, selector["link"]):
            sys.stderr.write("couldn't find link\n")
            continue

        if "parent_process" in selector:
            if not selector["parent_process"](myjson, a):
                continue

        entry = {}

        link = get_article_url(urllib.parse.urljoin(myjson["url"], clean_url(strify(extra_select(a, selector["link"])[0]["href"]))))
        entry["url"] = link

        if not link.strip():
            sys.stderr.write("empty link\n")
            # empty link
            continue

        date = 0
        if "date" in selector:
            if selector["date"] == "-1":
                date = parse_date(-1)
            else:
                date_tags = extra_select(a, selector["date"])
                if len(date_tags) == 1 and type(date_tags[0]) == str:
                    date = parse_date(date_tags[0])
                else:
                    for date_tag in date_tags:#a.select(selector["date"]):
                        try:
                            date = parse_date_tz(myjson, soup, strify(date_tag.text))
                            if date:
                                break
                        except Exception as e:
                            sys.stderr.write("couldn't parse date\n")
                            pass
        entry["date"] = date

        realcaption = None
        caption = None
        aid = ""
        if "aid" in selector:
            aid = strify(selector["aid"](a)) + " "
        if "caption" in selector:
            caption_el = extra_select(a, selector["caption"])[0]
            if type(caption_el) == str:
                realcaption = caption_el
            else:
                realcaption = strify(caption_el.text)
            realcaption = realcaption.strip()
            caption = aid + realcaption
        entry["media_caption"] = caption
        entry["caption"] = realcaption
        entry["similarcaption"] = realcaption

        description = None
        if "description" in selector:
            description_tag = extra_select(a, selector["description"])#a.select(selector["description"])
            description = ""
            for tag in description_tag:
                if len(tag.text)  > len(description):
                    description = strify(tag.text)
        else:
            description = realcaption
            if not "html" in selector:
                selector["html"] = True
        entry["description"] = description

        author = get_author(link)
        entry["author"] = author

        imagedata = None
        if "imagedata" in selector:
            imagedata = selector["imagedata"](entry, a)

        images = []
        if "images" in selector:
            image_tags = extra_select(a, selector["images"])
            for image in image_tags:
                if type(image) is str:
                    image_src = strify(image)
                else:
                    image_src = strify(image["src"])
                image_full_url = urllib.parse.urljoin(myjson["url"], image_src)
                image_max_url = get_max_quality(image_full_url, imagedata)
                images.append(strify(image_max_url))

        entry["images"] = images
        entry["videos"] = []

        if "is_valid" in selector:
            if not selector["is_valid"](a):
                continue

        #if "html" in selector:
        #    if selector["html"] is True:
        #        selector["html"] = lambda entry: "<p>" + entry["description"] + "</p>" + '\n'.join(["<p><img src='" + x + "' /></p>" for x in entry["images"]])
        #    entry["description"] = selector["html"](entry)

        articles.append(entry)

    return articles


def get_max_quality(url, data=None):
    url = strify(url)

    if "cp.news.search.daum.net/api/publish.json" in url:
        return None

    if "naver." in url:
        url = re.sub("\?.*", "", url)
        #if "imgnews" not in url:
        # do blogfiles

    if ".joins.com" in url:
        url = re.sub("\.tn_.*", "", url)

    if "image.news1.kr" in url:
        url = [re.sub("/[^/.]*\.([^/]*)$", "/original.\\1", url), url]

    if "main.img.topstarnews.net" in url:
        url = url.replace("main.img.topstarnews.net", "uhd.img.topstarnews.net")

    if "uhd.img.topstarnews.net/" in url:
        url = url.replace("/file_attach_thumb/", "/file_attach/")
        url = re.sub(r"_[^/]*[0-9]*x[0-9]*_[^/]*(\.[^/]*)$", "-org\\1", url)

    if "thumb.mtstarnews.com/" in url:
        url = re.sub(r"\.com/[0-9][0-9]/", ".com/06/", url)

    if ("stardailynews.co.kr" in url
        or "liveen.co.kr" in url
        or "munhwanews.com" in url
        or "ilyoseoul.co.kr" in url
        or "zenithnews.com" in url):
        url = re.sub("/thumbnail/", "/photo/", url)
        url = re.sub(r"_v[0-9]*\.", ".", url)
        baseurl = url

        url = [baseurl, re.sub("\.jpg$", ".gif", baseurl)]

    if "tvdaily.asiae.co.kr" in url or "chicnews.mk.co.kr":
        if data:
            url = url.replace("/tvdaily.asiae", "/image.tvdaily")
            url = url.replace("/thumb/", "/gisaimg/" + data["date"][:6] + "/")
            url = re.sub(r"/[a-zA-Z]*([^/]*)\.[^/]*$", "/" + data["aid"][:10] + "_\\1.jpg", url)

    if "img.hankyung.com" in url:
        url = re.sub(r"\.[0-9]\.([a-zA-Z0-9]*)$", ".1.\\1", url)

    if "img.tenasia.hankyung.com" in url or "hot-korea.net" in url:
        url = re.sub(r"-[0-9]*x[0-9]*\.jpg$", ".jpg", url)

    if "chosun.com" in url:
        url = url.replace("/thumb_dir/", "/img_dir/").replace("/thumbnail/", "/image/").replace("_thumb.", ".")

    if "file.osen.co.kr" in url:
        url = url.replace("/article_thumb/", "/article/")
        url = re.sub(r"_[0-9]*x[0-9]*\.jpg$", ".jpg", url)

    if "img.mbn.co.kr" in url:
        url = re.sub(r"_[^_/?&]*x[0-9]*\.([^_/?&])", ".\\1", url)
        url = re.sub(r"_s[0-9]*\.([^_/?&])", ".\\1", url)

    if "cdn.newsen.com" in url:
        url = url.replace("_ts.gif", ".jpg")

    if "photo.hankooki.com" in url:
        url = url.replace("/photo/", "/original/").replace("/arch/thumbs/", "/arch/original/")
        url = re.sub(r"/(.*\/)t([0-9]*[^/]*)$/", "\\1\\2", url)

    if ".ettoday.net" in url:
        url = re.sub(r"/[a-z]*([0-9]*\.[^/]*)$", "/\\1", url)

    if "xportsnews.com" in url:
        url = re.sub(r"/thm_([^/]*)", "/\\1", url)

    #if "img.sbs.co.kr" in url:
    #    url = re.sub(r"_[0-9]*(\.[^/]*)$", "\\1", url)

    if "res.heraldm.com" in url:
        url = re.sub(r"([^A-Za-z0-9_])idx=[0-9]*", "\\1idx=6", url)

    if "inews24.com" in url:
        url = url.replace("/thumbnail/", "/")

    if "yonhapnews.co.kr" in url:
        url = re.sub(r"(.*/[^/]*)_T(\.[^/]*)$", "\\1_P4\\2", url)

    if "cgeimage.commutil.kr" in url:
        url = re.sub(r"setimgmake\.php\?.*?simg=", "allidxmake.php?idx=3&simg=", url)

    if "hot-korea.net" in url:
        url = url.replace("thumbs/thumbs_", "")

    if "dimg.donga.com" in url:
        url = re.sub(r"/i/[0-9]*/[0-9]*/[0-9]*/wps", "/wps", url)

    if "img.saostar.vn" in url:
        url = re.sub(r"saostar.vn/[a-z][0-9]+/", "saostar.vn/", url)
        url = re.sub(r"saostar.vn/[0-9]+x[0-9]+/", "saostar.vn/", url)

    if ("images.sportskhan.net" in url or
        "img.khan.co.kr" in url):
        url = re.sub(r"\/r\/[0-9]+x[0-9]+\/", "/", url)
        url = re.sub(r"\/[a-z]*_([0-9]+\.[a-z0-9A-Z]*)$", "/\\1", url)

    if "ojsfile.ohmynews.com" in url:
        newurl = re.sub("\?.*", "", url)
        newurl = re.sub("/CT_T_IMG/(.*?)/([^/]*)_APP(\.[^/.]*?)(?:\?.*)?$", "/ORG_IMG_FILE/\\1/\\2_ORG\\3", newurl)
        newurl = re.sub("/[A-Z]*_IMG_FILE/(.*?)/([^/]*)_[A-Z]*(\.[^/.]*)(?:\?.*)?$", "/ORG_IMG_FILE/\\1/\\2_ORG\\3", newurl)
        url = [newurl, url]

    return url


def do_article_list(config, articles, myjson):
    article_i = 1
    quick = config.get("quick", False)
    #print(len(articles))
    for article in articles:
        if article is None:
            sys.stderr.write("error with article\n")
            continue
        if quick:
            if not article["caption"]:
                sys.stderr.write("no caption\n")
                return
            if article["date"] == 0:
                sys.stderr.write("no date\n")
                return
            if not article["caption"] or article["date"] == 0:
                sys.stderr.write("no salvageable information from search\n")
                sys.stderr.write(pprint.pformat(article) + "\n")
                return

            if not article["author"]:
                article["author"] = myjson["author"]
            elif article["author"] != myjson["author"]:
                sys.stderr.write("different authors\n")
                return

            myjson["entries"].append(article)
            continue
        article_url = article["url"]
        basetext = "(%i/%i) " % (article_i, len(articles))
        article_i += 1

        sys.stderr.write(basetext + "Downloading %s... " % article_url)
        sys.stderr.flush()

        newjson = None
        try:
            newjson = do_url(config, article_url, article)
        except Exception as e:
            sys.stderr.write("exception: " + str(e) + "\n")
            pass
        if not newjson:
            sys.stderr.write("url: " + article_url + " is invalid\n")
            continue

        if newjson["author"] != myjson["author"]:
            sys.stderr.write("current:\n\n" +
                             pprint.pformat(myjson) +
                             "\n\nnew:\n\n" +
                             pprint.pformat(newjson))
            continue

        sys.stderr.write("done\n")
        sys.stderr.flush()

        myjson["entries"].extend(newjson["entries"])
    return myjson


def do_url(config, url, oldarticle=None):
    quick = False
    if "quick" in config and config["quick"]:
        quick = True

    url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]")

    if "post" in config and config["post"]:
        data = rssit.util.download(url, post=config["post"], config=config)
    else:
        data = rssit.util.download(url, config=config)

    soup = bs4.BeautifulSoup(data, 'lxml')

    encoding = "utf-8"
    try:
        encoding = get_encoding(soup)
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        pass
    #data = data.decode("utf-8", "ignore")
    if type(data) != str and False:
        data = data.decode(encoding, "ignore")
        soup = bs4.BeautifulSoup(data, 'lxml')
    #data = download("file:///tmp/naver.html")

    #soup = bs4.BeautifulSoup(data, 'lxml')

    myjson = {
        "title": None,
        "author": None,
        "url": url,
        "config": {
            "generator": "news"
        },
        "entries": []
    }

    author = get_author(url)

    if not author:
        sys.stderr.write("unknown site\n")
        return

    myjson["author"] = author
    myjson["title"] = author

    newurl = get_redirect(myjson, soup)
    if newurl:
        return do_url(config, newurl, oldarticle)

    articles = get_articles(config, myjson, soup)
    if articles is not None:
        return do_article_list(config, articles, myjson)

    title = get_title(myjson, soup)

    if not title:
        sys.stderr.write("no title\n")
        return

    date = get_date(myjson, soup)

    if not date:
        if oldarticle and "date" in oldarticle and oldarticle["date"]:
            date = oldarticle["date"]
        else:
            sys.stderr.write("no date\n")
            return

    if "albums" in config and config["albums"] or is_album(myjson, soup):
        album = "[" + str(date.year)[-2:] + str(date.month).zfill(2) + str(date.day).zfill(2) + "] " + title
    else:
        album = None

    images = get_images(myjson, soup)
    if not images:
        sys.stderr.write("no images\n")
        images = []
        #return

    description = get_description(myjson, soup)
    if not description:
        sys.stderr.write("no description\n")

    if oldarticle:
        ourentry = oldarticle
    else:
        ourentry = {}

    ourentry.update({
        "caption": strify(title),
        "description": strify(description),
        "album": strify(album),
        "url": strify(url),
        "date": date,
        "author": strify(author),
        "images": images,
        "videos": [] # for now
    })

    nextpage = get_nextpage(myjson, soup)
    if nextpage and not quick:  # quick for now
        sys.stderr.write("Downloading next page... ")
        newjson = do_url(rssit.util.simple_copy(config), nextpage, rssit.util.simple_copy(oldarticle))
        if (newjson["author"] == myjson["author"] and
            len(newjson["entries"]) == 1 and
            newjson["entries"][0]["caption"] == ourentry["caption"]):
            sys.stderr.write("merging\n")
            newentry = newjson["entries"][0]
            if newentry["description"]:
                if ourentry["description"]:
                    ourentry["description"] += "<br /><hr /><br />" + newentry["description"]
                else:
                    ourentry["description"] = newentry["description"]

            #sys.stderr.write(url + "\n" + str(ourentry["images"]) + "\n")
            #sys.stderr.write(nextpage + "\n" + str(newentry["images"]) + "\n")
            if newentry["images"]:
                for i in newentry["images"]:
                    if i not in ourentry["images"]:
                        ourentry["images"].append(i)
        else:
            sys.stderr.write("ignoring\n")

    myjson["entries"].append(ourentry)

    return myjson


def generate_url(config, url):
    socialjson = do_url(config, url)
    return generate_base(config, socialjson)

def generate_api(config, url):
    socialjson = do_api(config, url)
    return generate_base(config, socialjson)

def generate_base(config, socialjson):
    retval = {
        "social": socialjson
    }

    basefeedjson = rssit.util.simple_copy(socialjson)
    for entry in basefeedjson["entries"]:
        if "realcaption" in entry:
            entry["caption"] = entry["realcaption"]

    feedjson = rssit.converters.social_to_feed.process(basefeedjson, config)

    return {
        "social": socialjson,
        "feed": feedjson
    }


def process(server, config, path):
    if path.startswith("/post/"):
        if "/endpost/" not in config["fullpath"]:
            sys.stderr.write("no /endpost/\n")
            return None
        config["post"] = re.sub(".*?/post/(.*?)/endpost/.*", "\\1", config["fullpath"]).encode("utf-8")
        newpath = re.sub(".*?/endpost", "", path)
        config["fullpath"] = re.sub(".*?/endpost", "", config["fullpath"])
        return process(server, config, newpath)
    if path.startswith("/url/"):
        url = "http://" + re.sub(".*?/url/", "", config["fullpath"])
        return generate_url(config, url)
    elif path.startswith("/qurl/"):
        url = "http://" + re.sub(".*?/qurl/", "", config["fullpath"])
        config["quick"] = True
        return generate_url(config, url)
    elif path.startswith("/api/"):
        return generate_api(config, path)


infos = [{
    "name": "news",
    "display_name": "News",

    "config": {
        "albums": {
            "name": "Albums",
            "description": "Create albums for articles",
            "value": False
        }
    },

    "get_url": get_url,
    "process": process
}]
