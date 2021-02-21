# -*- coding: utf-8 -*-
# RSScrawler
# Projekt von https://github.com/rix1337

import json
import re
from bs4 import BeautifulSoup

from rsscrawler.common import add_decrypt
from rsscrawler.common import check_hoster
from rsscrawler.common import rreplace
from rsscrawler.config import RssConfig
from rsscrawler.url import get_redirected_url
from rsscrawler.url import get_url
from rsscrawler.url import get_urls_async
from rsscrawler.url import post_url_headers


class FakeFeedParserDict(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("No such attribute: " + name)


def unused_get_feed_parameter(param):
    return param


def get_download_links(self, content, title):
    unused_get_feed_parameter(title)
    url_hosters = re.findall(r'href="([^"\'>]*)".+?(.+?)<', content)
    links = {}
    for url_hoster in reversed(url_hosters):
        hoster = url_hoster[1].lower().replace('target="_blank">', '').replace(" ", "-").replace("ddownload", "ddl")
        if check_hoster(hoster, self.configfile):
            link = url_hoster[0]
            if self.url in link:
                demasked_link = get_redirected_url(link, self.configfile, self.dbfile, self.scraper)
                if demasked_link:
                    link = demasked_link
            links[hoster] = link
    if self.hoster_fallback and not links:
        for url_hoster in reversed(url_hosters):
            hoster = url_hoster[1].lower().replace('target="_blank">', '').replace(" ", "-").replace("ddownload", "ddl")
            link = url_hoster[0]
            if self.url in link:
                demasked_link = get_redirected_url(link, self.configfile, self.dbfile, self.scraper)
                if demasked_link:
                    link = demasked_link
            links[hoster] = link
    return list(links.values())


def add_decrypt_instead_of_download(configfile, dbfile, device, key, path, download_links, password):
    unused_get_feed_parameter(configfile)
    unused_get_feed_parameter(path)

    if add_decrypt(key, download_links[0], password, dbfile):
        return device
    else:
        return False


def by_get_download_links(self, content, title):
    async_link_results = re.findall(r'href="([^"\'>]*)"', content)
    async_link_results = get_urls_async(async_link_results, self.configfile, self.dbfile, self.scraper)

    content = []
    links = async_link_results[0]
    for link in links:
        link = BeautifulSoup(link, 'lxml').find("a", href=re.compile("/go\.php\?"))
        try:
            content.append('href="' + link["href"] + '">' + link.text.replace(" ", "") + '<')
        except:
            pass

    content = "".join(content)
    download_links = get_download_links(self, content, title)
    return download_links


def by_feed_enricher(self, content):
    base_url = "https://" + RssConfig('Hostnames', self.configfile).get('by')
    content = BeautifulSoup(content, 'lxml')
    posts = content.findAll("a", href=re.compile("/category/"), text=re.compile("Download"))
    async_results = []
    for post in posts:
        try:
            async_results.append(base_url + post['href'])
        except:
            pass
    async_results = get_urls_async(async_results, self.configfile, self.dbfile, self.scraper)
    results = async_results[0]

    entries = []
    if results:
        for result in results:
            try:
                content = []
                details = BeautifulSoup(result, 'lxml').findAll("td", {"valign": "TOP", "align": "CENTER"})[1]
                title = details.find("small").text
                published = details.find("th", {"align": "RIGHT"}).text
                try:
                    imdb = details.find("a", href=re.compile("imdb.com"))
                    imdb_link = imdb["href"].replace("https://anonym.to/?", "")
                    imdb_score = imdb.text.replace(" ", "").replace("/10", "")
                    if "0.0" in imdb_score:
                        imdb_score = "9.9"
                    content.append('<a href="' + imdb_link + '"' + imdb_score + '</a>')
                except:
                    pass
                links = details.find_all("iframe")
                for link in links:
                    content.append('href="' + link["src"] + '"')

                content = "".join(content)

                entries.append(FakeFeedParserDict({
                    "title": title,
                    "published": published,
                    "content": [FakeFeedParserDict({
                        "value": content + " mkv"})]
                }))
            except:
                pass

    feed = {"entries": entries}
    feed = FakeFeedParserDict(feed)
    return feed


def by_search_results(content, base_url):
    content = BeautifulSoup(content, 'lxml')
    posts = content.findAll("a", href=re.compile("/category/"))
    results = []
    for post in posts:
        try:
            title = post.text.replace(" ", ".")
            link = "https://" + base_url + post['href']
            results.append([title, link])
        except:
            pass
    return results


def dw_get_download_links(self, content, title):
    unused_get_feed_parameter(title)
    try:
        download_link = False
        hosters = re.findall(r'HOSTERS="(.*)"', content)[0].split("|")
        for hoster in hosters:
            hoster = hoster.lower().replace("ddownload", "ddl")
            if check_hoster(hoster, self.configfile):
                download_link = re.findall(r'DOWNLOADLINK="(.*)"HOSTERS="', content)[0]
        if self.hoster_fallback and not download_link:
            download_link = re.findall(r'DOWNLOADLINK="(.*)"HOSTERS="', content)[0]
    except:
        return False
    return [download_link]


def dw_feed_enricher(self, content):
    base_url = "https://" + RssConfig('Hostnames', self.configfile).get('dw')
    content = BeautifulSoup(content, 'lxml')
    posts = content.findAll("a", href=re.compile("download/"))
    href_by_id = {}
    async_results = []
    for post in posts:
        try:
            post_id = post['href'].replace("download/", "").split("/")[0]
            post_link = base_url + "/" + post['href']
            post_hosters = post.parent.findAll("img", src=re.compile(r"images/icon_hoster"))
            hosters = []
            for hoster in post_hosters:
                hosters.append(hoster["title"].replace("Download bei ", ""))
            hosters = "|".join(hosters)
            href_by_id[post_id] = {
                "hosters": hosters,
                "link": post_link
            }
            async_results.append(post_link)
        except:
            pass
    async_results = get_urls_async(async_results, self.configfile, self.dbfile, self.scraper)
    results = async_results[0]

    entries = []
    if results:
        for result in results:
            try:
                content = []
                details = BeautifulSoup(result, 'lxml')
                title = details.title.text.split(' //')[0].replace("*mirror*", "").strip()
                post_id = details.find("a", {"data-warezkorb": re.compile(r"\d*")})["data-warezkorb"]
                details = details.findAll("div", {"class": "row"})[3]
                published = details.findAll("td")[1].text.replace("Datum", "")
                try:
                    imdb = details.findAll("td")[6].find("a")
                    imdb_link = imdb["href"]
                    imdb_score = imdb.find("b").text.replace(" ", "").replace("/10", "")
                    if "0.0" in imdb_score:
                        imdb_score = "9.9"
                    content.append('<a href="' + imdb_link + '"' + imdb_score + '</a>')
                except:
                    pass

                content.append('DOWNLOADLINK="' + href_by_id[post_id]["link"] + '"')
                content.append('HOSTERS="' + href_by_id[post_id]["hosters"] + '"')

                content = "".join(content)

                entries.append(FakeFeedParserDict({
                    "title": title,
                    "published": published,
                    "content": [FakeFeedParserDict({
                        "value": content + " mkv"})]
                }))
            except:
                pass

    feed = {"entries": entries}
    feed = FakeFeedParserDict(feed)
    return feed


def fx_content_to_soup(content):
    content = BeautifulSoup(content, 'lxml')
    return content


def fx_get_download_links(self, content, title):
    hostnames = RssConfig('Hostnames', self.configfile)
    fc = hostnames.get('fc').replace('www.', '').split('.')[0]
    try:
        try:
            content = BeautifulSoup(content, 'lxml')
        except:
            content = BeautifulSoup(str(content), 'lxml')
        try:
            download_links = [content.find("a", text=re.compile(r".*" + title + r".*"))['href']]
        except:
            if not fc:
                fc = '^unmatchable$'
                print(u"FC Hostname nicht gesetzt. FX kann keine Links finden!")
            download_links = re.findall(r'"(https://.+?' + fc + '.+?)"', str(content))
    except:
        return False
    return download_links


def fx_feed_enricher(self, feed):
    hostnames = RssConfig('Hostnames', self.configfile)
    fc = hostnames.get('fc').replace('www.', '').split('.')[0]
    if not fc:
        fc = '^unmatchable$'
        print(u"FC Hostname nicht gesetzt. FX kann keine Links finden!")

    feed = BeautifulSoup(feed, 'lxml')
    articles = feed.findAll("article")
    entries = []

    for article in articles:
        try:
            article = BeautifulSoup(str(article), 'lxml')
            titles = article.findAll("a", href=re.compile(fc))
            for title in titles:
                title = title.text.encode("ascii", errors="ignore").decode().replace("/", "")
                if title:
                    if "download" in title.lower():
                        try:
                            title = str(article.find("strong", text=re.compile(r".*Release.*")).nextSibling)
                        except:
                            continue
                    published = ""
                    dates = article.findAll("time")
                    for date in dates:
                        published = date["datetime"]
                    entries.append(FakeFeedParserDict({
                        "title": title,
                        "published": published,
                        "content": [
                            FakeFeedParserDict({
                                "value": str(article) + " mkv"
                            })]
                    }))
        except:
            print(u"FX hat den Feed angepasst. Parsen teilweise nicht möglich!")
            continue

    feed = {"entries": entries}
    feed = FakeFeedParserDict(feed)
    return feed


def fx_search_results(content, configfile, dbfile, scraper):
    hostnames = RssConfig('Hostnames', configfile)
    fc = hostnames.get('fc').replace('www.', '').split('.')[0]
    if not fc:
        fc = '^unmatchable$'
        print(u"FC Hostname nicht gesetzt. FX kann keine Links finden!")

    articles = content.find("main").find_all("article")
    result_urls = []
    for article in articles:
        url = article.find("a")["href"]
        if url:
            result_urls.append(url)

    items = []

    if result_urls:
        results = []
        for url in result_urls:
            results.append(get_url(url, configfile, dbfile, scraper))

        for result in results:
            article = BeautifulSoup(str(result), 'lxml')
            titles = article.find_all("a", href=re.compile(fc))
            for title in titles:
                link = article.find("link", rel="canonical")["href"]
                title = title.text.encode("ascii", errors="ignore").decode().replace("/", "")
                if title:
                    if "download" in title.lower():
                        try:
                            title = str(content.find("strong", text=re.compile(r".*Release.*")).nextSibling)
                        except:
                            continue
                    items.append([title, link + "|" + title])
    return items


def nk_feed_enricher(self, content):
    base_url = "https://" + RssConfig('Hostnames', self.configfile).get('nk')
    content = BeautifulSoup(content, 'lxml')
    posts = content.findAll("a", {"class": "btn"}, href=re.compile("/release/"))
    async_results = []
    for post in posts:
        try:
            async_results.append(base_url + post['href'])
        except:
            pass
    async_results = get_urls_async(async_results, self.configfile, self.dbfile, self.scraper)[0]

    entries = []
    if async_results:
        for result in async_results:
            try:
                content = []
                details = BeautifulSoup(result, 'lxml').find("div", {"class": "article"})
                title = details.find("span", {"class": "subtitle"}).text
                published = details.find("p", {"class": "meta"}).text
                content.append("mkv ")
                try:
                    imdb = details.find("a", href=re.compile("imdb.com"))["href"]
                    content.append('<a href="' + imdb + '" 9,9</a>')
                except:
                    pass
                links = details.find_all("a", href=re.compile("/go/"))
                for link in links:
                    content.append('href="' + base_url + link["href"] + '">' + link.text + '<')
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


def nk_search_results(content, base_url):
    content = BeautifulSoup(content, 'lxml')
    posts = content.findAll("a", {"class": "btn"}, href=re.compile("/release/"))
    results = []
    for post in posts:
        try:
            title = post.parent.parent.parent.find("span", {"class": "subtitle"}).text
            link = base_url + post['href']
            results.append([title, link])
        except:
            pass
    return results


def ww_post_url_headers(url, configfile, dbfile, headers=False, scraper=False):
    try:
        if not headers:
            headers = {}
        payload = url.split("|")
        url = payload[0]
        referer = payload[0].replace("/ajax", payload[1])
        data = payload[2]
        headers["Referer"] = referer
        response = post_url_headers(url, configfile, dbfile, headers, data, scraper)
        if not response[0].text or response[0].status_code is not (200 or 304) or not '<span class="main-rls">' in \
                                                                                      response[0].text:
            print(u"WW hat den Feed-Anruf blockiert. Eine spätere Anfrage hat möglicherweise Erfolg!")
            return ""
        return response
    except:
        return ""


def ww_get_download_links(self, content, title):
    base_url = "https://" + RssConfig('Hostnames', self.configfile).get('ww')
    content = content.replace("mkv|", "")
    download_links = []
    try:
        response = get_url(content, self.configfile, self.dbfile, self.scraper)
        if not response or "NinjaFirewall 429" in response:
            print(u"WW hat den Link-Abruf für " + title + " blockiert. Eine spätere Anfrage hat möglicherweise Erfolg!")
            return False
        links = BeautifulSoup(response, 'lxml').findAll("div", {"id": "download-links"})
        for link in links:
            hoster = link.text
            if 'Direct Download 100 MBit/s' not in hoster:
                url = base_url + link.find("a")["href"]
                download_links.append('href="' + url + '" ' + hoster + '<')
        download_links = "".join(download_links)

        download_links = get_download_links(self, download_links, title)
        return download_links
    except:
        return False


def ww_feed_enricher(self, content):
    base_url = "https://" + RssConfig('Hostnames', self.configfile).get('ww')
    content = BeautifulSoup(content, 'lxml')
    posts = content.findAll("li")
    entries = []
    if posts:
        for post in posts:
            try:
                link = post.findAll("a", href=re.compile("/download"))[1]
                title = link.nextSibling.nextSibling.strip()
                published = post.find("span", {"class": "main-date"}).text.replace("\n", "")
                content = "mkv|" + base_url + link["href"]

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


def j_releases_to_feedparser_dict(releases, list_type, base_url, check_seasons_or_episodes):
    releases = json.loads(releases)
    entries = []

    for release in releases:
        if check_seasons_or_episodes:
            try:
                if list_type == 'seasons' and release['episode']:
                    continue
                elif list_type == 'episodes' and not release['episode']:
                    continue
            except:
                continue
        title = release['name']
        series_url = base_url + '/serie/' + release["_media"]['slug']
        published = release['createdAt']

        entries.append(FakeFeedParserDict({
            "title": title,
            "series_url": series_url,
            "published": published
        }))

    feed = {"entries": entries}
    feed = FakeFeedParserDict(feed)
    return feed


def sf_releases_to_feedparser_dict(releases, list_type, base_url, check_seasons_or_episodes):
    content = BeautifulSoup(releases, 'lxml')
    releases = content.findAll("div", {"class": "row"}, style=re.compile("order"))
    entries = []

    for release in releases:
        a = release.find("a", href=re.compile("/"))
        title = a.text
        is_episode = re.match(r'.*(S\d{1,3}E\d{1,3}).*', title)
        if check_seasons_or_episodes:
            try:
                if list_type == 'seasons' and is_episode:
                    continue
                elif list_type == 'episodes' and not is_episode:
                    continue
            except:
                continue

        series_url = rreplace(base_url + '/api/v1' + a['href'], '/', '/season/', 1)
        published = release.find("div", {"class": "datime"}).text

        entries.append(FakeFeedParserDict({
            "title": title,
            "series_url": series_url,
            "published": published
        }))

    feed = {"entries": entries}
    feed = FakeFeedParserDict(feed)
    return feed