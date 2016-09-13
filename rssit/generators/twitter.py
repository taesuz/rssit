# -*- coding: utf-8 -*-


import datetime
import re
import rssit.util
import bs4
import demjson


info = {
    "name": "Twitter",
    "codename": "twitter",
    "config": {
        "author_username": False
    }
}


def check(url):
    return re.match(r"^https?://(?:\w+\.)?twitter.com/(?P<user>[^/]*)", url) != None


def generate(config, path):
    match = re.match(r"^https?://(?:\w+\.)?twitter.com/(?P<user>[^/]*)", config["url"])

    if match == None:
        return None

    user = match.group("user")

    data = rssit.util.download(config["url"])

    soup = bs4.BeautifulSoup(data, 'lxml')

    author = "@" + user
    description = "%s's twitter" % author

    init_data = soup.select("#init-data")

    if len(init_data) > 0:
        init_data = init_data[0]

        if "value" in init_data.attrs:
            init_json = demjson.decode(init_data.attrs["value"])

            if not config["author_username"]:
                if len(init_json["profile_user"]["name"]) > 0:
                    author = init_json["profile_user"]["name"]

            if len(init_json["profile_user"]["description"]) > 0:
                description = init_json["profile_user"]["description"]

    feed = {
        "title": author,
        "description": description,
        "author": user,
        "social": True,
        "entries": []
    }

    for tweet in soup.find_all(attrs={"data-tweet-id": True}):
        timestamp = int(tweet.find_all(attrs={"data-time": True})[0]["data-time"])
        date = rssit.util.localize_datetime(datetime.datetime.fromtimestamp(timestamp, None))

        username = tweet["data-screen-name"]

        link = tweet["data-permalink-path"]

        caption = ""

        for text in tweet.select("p.tweet-text"):
            for i in text.children:
                if type(i) is bs4.element.NavigableString:
                    caption += str(i.string)
                else:
                    if i.name == "img":
                        caption += i["alt"]
                    elif i.name == "a":
                        if "data-expanded-url" in i.attrs:
                            a_url = i["data-expanded-url"]
                            caption += a_url
                        elif "twitter-hashtag" in i["class"]:
                            caption += "#" + i.b.string

        image_holder = tweet.find_all(attrs={"data-image-url": True})

        if len(image_holder) > 0:
            images = []

            for image in image_holder:
                image_url = image["data-image-url"]
                images.append(image_url)
        else:
            images = None

        is_video_el = tweet.select(".AdaptiveMedia-video")
        if len(is_video_el) > 0:
            tweet_id = tweet["data-tweet-id"]
            video_url = "https://twitter.com/i/videos/%s" % tweet_id
            pmp = tweet.select(".PlayableMedia-player")[0]
            preview_url = re.search(r"background-image: *url.'(?P<url>.*?)'",
                                   pmp["style"]).group("url")

            videos = [{
                "image": preview_url,
                "video": video_url
            }]
        else:
            videos = None

        feed["entries"].append({
            "url": link,
            "caption": caption,
            "author": username,
            "date": date,
            "images": images,
            "videos": videos
        })

    return feed
