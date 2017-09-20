# -*0 coding: utf-8 -*-


import re
import rssit.util
import ujson
import pprint
import sys
import urllib.parse
import html
import datetime


def get_url(url):
    if "reddit.com" not in url or ".json" not in url:
        return None

    return "/json/" + re.sub(r"^(https?://)?([a-zA-Z]*\.)?reddit\.com/", "", url)


def generate_json(config, url):
    data = rssit.util.download(url, config=config)
    #print(data)
    jsondata = ujson.loads(data)

    myjson = {
        "title": "reddit", # FIXME
        "author": "reddit",
        "url": url,
        "config": {
            "generator": "reddit"
        },
        "entries": []
    }

    nodes = jsondata["data"]["children"]
    for node_ in nodes:
        node = node_["data"]
        kind = node_["kind"]

        #pprint.pprint(node)

        title = "[/u/" + node["author"] + "] " + node["subject"]
        if "link_title" in node:
            title += ": " + node["link_title"]

        title = title.strip()

        link = ""

        if "context" in node:
            link = node["context"]

        if not link or len(link) == 0:
            if kind == "t4":
                link = "/message/messages/" + node["id"]
            else:
                sys.stderr.write("WARNING: Unsupported kind: " + kind + "\n")
                link = "/" + node["name"]

        url = urllib.parse.urljoin(url, link)

        date = rssit.util.utc_datetime(datetime.datetime.utcfromtimestamp(node["created_utc"]))
        content = html.unescape(node["body_html"])

        myjson["entries"].append({
            "url": url,
            "title": title,
            "author": node["author"],
            "date": date,
            "content": content
        })

    #pprint.pprint(myjson)
    return ("feed", myjson)

def process(server, config, path):
    if path.startswith("/json/"):
        url = "http://www.reddit.com/" + re.sub(r".*?/json/", "", config["fullpath"])
        return generate_json(config, url)


infos = [{
    "name": "reddit",
    "display_name": "Reddit",

    "config": {},

    "get_url": get_url,
    "process": process
}]