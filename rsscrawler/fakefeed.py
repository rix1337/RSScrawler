# -*- coding: utf-8 -*-
# RSScrawler
# Projekt von https://github.com/rix1337


import re

import feedparser
from bs4 import BeautifulSoup

from rsscrawler.url import get_url
from rsscrawler.url import get_urls_asynch


class FakeFeedParserDict(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("No such attribute: " + name)


def hs_feed_enricher(feed, configfile):
    feed = feedparser.parse(feed)

    asynch_results = []
    for post in feed.entries:
        try:
            asynch_results.append(post.links[0].href)
        except:
            pass
    asynch_results = get_urls_asynch(asynch_results, configfile)

    entries = []
    if asynch_results:
        for result in asynch_results:
            try:
                content = []
                details = result
                title = BeautifulSoup(details, 'lxml').find("h2", {"class": "entry-title"}).text
                published = BeautifulSoup(details, 'lxml').find("p", {"class": "blog-post-meta"}).contents[0]
                data = BeautifulSoup(details, 'lxml').find("div", {"class": "entry-content"}).contents[2]
                content.append(str(data).replace("\n", ""))
                content = "".join(content)

                entries.append(FakeFeedParserDict({
                    "title": title,
                    "published": published,
                    "content": [FakeFeedParserDict({
                        "value": content})]
                }))
            except:
                pass

    feed = {"entries": entries}
    feed = FakeFeedParserDict(feed)
    return feed


def hs_search_to_soup(url, configfile, dbfile):
    content = []
    search = BeautifulSoup(get_url(url, configfile, dbfile), 'lxml')
    if search:
        results = search.find_all("item")
        if results:
            for r in results:
                try:
                    title = r.title.next
                    details = BeautifulSoup(get_url(r.link.next, configfile, dbfile), 'lxml')
                    content.append({
                        "key": title,
                        "value": details
                    })
                except:
                    pass
    return hs_search_to_feedparser_dict(content)


def hs_search_to_feedparser_dict(beautifulsoup_object_list):
    entries = []
    for beautifulsoup_object in beautifulsoup_object_list:
        title = beautifulsoup_object["key"]
        item_head = beautifulsoup_object["value"].find_all("p", {"class": "blog-post-meta"})
        item_download = beautifulsoup_object["value"].find_all("div", {"class": "entry-content"})

        i = 0
        for item in item_head:
            contents = item_download[i].contents
            published = item.contents[0]
            content = []
            data = contents[2]
            content.append(str(data).replace("\n", ""))
            content = "".join(content)

            entries.append(FakeFeedParserDict({
                "title": title,
                "published": published,
                "content": [FakeFeedParserDict({
                    "value": content})]
            }))

            i += 1

    feed = {"entries": entries}
    feed = FakeFeedParserDict(feed)
    return feed


def hs_search_results(url):
    content = []
    search = BeautifulSoup(url, 'lxml')
    if search:
        results = search.find_all("item")
        if results:
            for r in results:
                try:
                    title = r.title.next
                    link = r.contents[2]
                    content.append((title, link))
                except:
                    break
    return content


def dj_to_feedparser_dict(beautifulsoup_object):
    content_areas = beautifulsoup_object.findAll("fieldset")
    entries = []

    for area in content_areas:
        try:
            published = re.findall(r"Updates.{3}(.*Uhr)", area.text)[0]
        except:
            published = "ERROR"

        genres = area.find_all("div", {"class": "grey-box"})

        for genre in genres:
            items = genre.select("a")
            dj_type = str(genre.previous.previous)

            for item in items:
                titles = item.text.split('\n')
                link = item.attrs["href"]

                for title in titles:
                    entries.append(FakeFeedParserDict({
                        "title": title,
                        "published": published,
                        "genre": dj_type,
                        "link": link
                    }))

    feed = {"entries": entries}
    feed = FakeFeedParserDict(feed)
    return feed


def dj_content_to_soup(content):
    content = BeautifulSoup(content, 'lxml')
    content = dj_to_feedparser_dict(content)
    return content
