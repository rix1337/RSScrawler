# -*- coding: utf-8 -*-
# RSScrawler
# Projekt von https://github.com/rix1337

import cloudscraper
import logging
import re
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from rsscrawler.common import check_is_site
from rsscrawler.common import encode_base64
from rsscrawler.common import sanitize
from rsscrawler.config import RssConfig
from rsscrawler.sites.shared.fake_feed import by_search_results
from rsscrawler.sites.shared.fake_feed import dw_search_results
from rsscrawler.sites.shared.fake_feed import fx_content_to_soup
from rsscrawler.sites.shared.fake_feed import fx_search_results
from rsscrawler.sites.shared.fake_feed import nk_search_results
from rsscrawler.url import get_url
from rsscrawler.url import get_urls_async
from rsscrawler.url import post_url

logger = logging.getLogger('rsscrawler')


def get(title, configfile, dbfile, bl_only=False, sj_only=False):
    hostnames = RssConfig('Hostnames', configfile)
    by = hostnames.get('by')
    dw = hostnames.get('dw')
    fx = hostnames.get('fx')
    nk = hostnames.get('nk')
    sj = hostnames.get('sj')

    specific_season = re.match(r'^(.*),(s\d{1,3})$', title.lower())
    specific_episode = re.match(r'^(.*),(s\d{1,3}e\d{1,3})$', title.lower())
    if specific_season:
        split = title.split(",")
        title = split[0]
        special = split[1].upper()
    elif specific_episode:
        split = title.split(",")
        title = split[0]
        special = split[1].upper()
    else:
        special = None

    bl_final = {}
    sj_final = {}
    scraper = cloudscraper.create_scraper()

    if not sj_only:
        mb_query = sanitize(title).replace(" ", "+")
        if special:
            bl_query = mb_query + "+" + special
        else:
            bl_query = mb_query

        unrated = []

        config = RssConfig('MB', configfile)
        quality = config.get('quality')
        ignore = config.get('ignore')

        if "480p" not in quality:
            search_quality = "+" + quality
        else:
            search_quality = ""

        if by:
            by_search = 'https://' + by + '/?q=' + bl_query + search_quality
        else:
            by_search = None
        if dw:
            dw_search = 'https://' + dw + '/?kategorie=Movies&search=' + bl_query + search_quality
        else:
            dw_search = None
        if fx:
            fx_search = 'https://' + fx + '/?s=' + bl_query
        else:
            fx_search = None

        async_results = get_urls_async([by_search, dw_search, fx_search], configfile, dbfile, scraper)
        scraper = async_results[1]
        async_results = async_results[0]

        by_results = []
        dw_results = []
        fx_results = []

        for res in async_results:
            if check_is_site(res, configfile) == 'BY':
                by_results = by_search_results(res, by)
            elif check_is_site(res, configfile) == 'DW':
                dw_results = dw_search_results(res, dw)
            elif check_is_site(res, configfile) == 'FX':
                fx_results = fx_search_results(fx_content_to_soup(res), configfile, dbfile, scraper)

        if nk:
            nk_search = post_url('https://' + nk + "/search", configfile, dbfile,
                                 data={'search': bl_query.replace("+", " ") + " " + quality})
            nk_results = nk_search_results(nk_search, 'https://' + nk + '/')
        else:
            nk_results = []

        password = by
        for result in by_results:
            if "480p" in quality:
                if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[
                    0].lower() or "2160p" in \
                        result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                    0].lower() or "complete.uhd.bluray" in result[0].lower():
                    continue
            if "xxx" not in result[0].lower():
                unrated.append(
                    [rate(result[0], ignore), encode_base64(result[1] + "|" + password), result[0] + " (BY)"])

        password = dw
        for result in dw_results:
            if "480p" in quality:
                if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[
                    0].lower() or "2160p" in \
                        result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                    0].lower() or "complete.uhd.bluray" in result[0].lower():
                    continue
            unrated.append(
                [rate(result[0], ignore), encode_base64(result[1] + "|" + password), result[0] + " (DW)"])

        password = fx.split('.')[0]
        for result in fx_results:
            if "480p" in quality:
                if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[
                    0].lower() or "2160p" in \
                        result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                    0].lower() or "complete.uhd.bluray" in result[0].lower():
                    continue
            if "-low" not in result[0].lower():
                unrated.append(
                    [rate(result[0], ignore), encode_base64(result[1] + "|" + password), result[0] + " (FX)"])

        password = nk.split('.')[0].capitalize()
        for result in nk_results:
            if "480p" in quality:
                if "720p" in result[0].lower() or "1080p" in result[0].lower() or "1080i" in result[
                    0].lower() or "2160p" in \
                        result[0].lower() or "complete.bluray" in result[0].lower() or "complete.mbluray" in result[
                    0].lower() or "complete.uhd.bluray" in result[0].lower():
                    continue
            unrated.append(
                [rate(result[0], ignore), encode_base64(result[1] + "|" + password), result[0] + " (NK)"])

        rated = sorted(unrated, reverse=True)

        results = {}
        i = 0

        for result in rated:
            res = {"payload": result[1], "title": result[2]}
            results["result" + str(i + 1000)] = res
            i += 1
        bl_final = results

    if not bl_only:
        if sj:
            sj_query = sanitize(title).replace(" ", "+")
            sj_search = get_url('https://' + sj + '/serie/search?q=' + sj_query, configfile, dbfile, scraper)
            try:
                sj_results = BeautifulSoup(sj_search, 'lxml').findAll("a", href=re.compile("/serie"))
            except:
                sj_results = []
        else:
            sj_results = []

        if special:
            append = " (" + special + ")"
        else:
            append = ""
        i = 0
        results = {}
        for result in sj_results:
            r_title = result.text
            r_rating = fuzz.ratio(title.lower(), r_title)
            if r_rating > 40:
                res = {"payload": encode_base64(result['href'] + "|" + r_title + "|" + str(special)),
                       "title": r_title + append}
                results["result" + str(i + 1000)] = res
                i += 1
        sj_final = results

    return bl_final, sj_final


def rate(title, ignore=False):
    score = 0
    if ".bluray." in title.lower():
        score += 7
    if ".bd." in title.lower():
        score += 7
    if ".bdrip." in title.lower():
        score += 7
    if re.match(r'.*\-(4SJ|TVS)', title):
        score += 4
    if ".dl." in title.lower():
        score += 2
    if re.match(r'.*\.(DTS|DD\+*51|DD\+*71|AC3\.5\.*1)\..*', title):
        score += 2
    if re.match(r'.*\.(720|1080|2160)p\..*', title):
        score += 2
    if ".ml." in title.lower():
        score += 1
    if ".dd20." in title.lower():
        score += 1
    if "dubbed." in title.lower():
        score -= 1
    if ".synced." in title.lower():
        score -= 1
    if ".ac3d." in title.lower():
        score -= 1
    if ".dtsd." in title.lower():
        score -= 1
    if ".hdtv." in title.lower():
        score -= 1
    if ".dtv" in title.lower():
        score -= 1
    if ".pdtv" in title.lower():
        score -= 1
    if "tvrip." in title.lower():
        score -= 1
    if ".subbed." in title.lower():
        score -= 2
    if ".xvid." in title.lower():
        score -= 2
    if ".pal." in title.lower():
        score -= 10
    if "dvd9" in title.lower():
        score -= 10
    if ignore:
        try:
            ignore = ignore.replace(",", "|").lower() if len(ignore) > 0 else r"^unmatchable$"
        except TypeError:
            ignore = r"^unmatchable$"
        r = re.search(ignore, title.lower())
        if r:
            score -= 5
    if ".subpack." in title.lower():
        score -= 10
    return score
