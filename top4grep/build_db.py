import os
import re
from datetime import datetime
import time

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from . import Session
from .db import Paper
from .utils import new_logger

S2_API_KEY = os.getenv("S2_API_KEY", "")
S2_REQUESTS_PER_SECOND = 1

logger = new_logger("DB")

CONFERENCES = ["NDSS", "IEEE S&P", "USENIX", "CCS", "IEEE EuroS&P", "ACSAC",
               "RAID", "ESORICS", "AsiaCCS", "PETS", "WWW"]
NAME_MAP = {
        "NDSS": ("ndss", "ndss"),
        "IEEE S&P": ("sp", "sp"),
        "USENIX": ("uss", "uss"),
        "CCS": ("ccs", "ccs"),
        "IEEE EuroS&P": ("eurosp", "eurosp"),
        "ACSAC": ("acsac", "acsac"),
        "RAID": ("raid", "raid"),
        "ESORICS": [("esorics", "esorics"), ("esorics", "esorics{YEAR}-1"), ("esorics", "esorics{YEAR}-2")],
        "AsiaCCS": [("ccs", "asiaccs"), ("asiaccs", "asiaccs")],
        "PETS": [("pet", "pet"), ("pet", "pets"), ("popets", "popets", "journals")],
        "WWW": ("www", "www"),
        }

def save_paper(conf, year, title, authors, abstract):
    session = Session()
    paper = Paper(conference=conf, year=year, title=title, authors=", ".join(authors), abstract=abstract)
    session.add(paper)
    session.commit()
    session.close()

def paper_exist(conf, year, title, authors):
    session = Session()
    paper = session.query(Paper).filter(Paper.conference==conf, Paper.year==year, Paper.title==title).first()
    session.close()
    return paper is not None

def paper_has_abstract(conf, year, title):
    session = Session()
    paper = session.query(Paper).filter(Paper.conference==conf, Paper.year==year, Paper.title==title).first()
    session.close()
    return paper is not None and paper.abstract != ""

def update_paper(conf, year, title, abstract):
    session = Session()
    paper = session.query(Paper).filter(Paper.conference==conf, Paper.year==year, Paper.title==title).first()
    paper.abstract = abstract
    session.commit()
    session.close()

def get_abstract(title, year):
    # https://www.zenrows.com/blog/python-requests-retry#use-existing-retry-wrapper
    retry_strategy = Retry(
        total=4,  # Maximum number of retries
        backoff_factor=2,  # Exponential backoff factor (e.g., 2 means 1, 2, 4, 8 seconds, ...)
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    r = session.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        headers={'X-API-KEY': S2_API_KEY},
        params={"query": title, "fieldsOfStudy": "Computer Science", "fields": "title,year,venue,abstract"},
        timeout=10
    )
    r.raise_for_status()
    data = r.json()
    if data["total"] == 0:
        print(f"Failed to find paper {title} at {year}")
        return ""

    # remove all the punctuations and spaces
    normalize_title = lambda title: re.sub(r"[^\w]", "", title.lower())

    found_paper = None
    original_title = title
    title = normalize_title(title)
    for paper in data["data"]:
        remote_title = normalize_title(paper['title'])
        if title == remote_title or title == remote_title:
            found_paper = paper
            break
    else:
        print(f"Warning: failed to find correct paper {original_title} at {year}")
        print(f"Found {data['total']} papers:")
        for paper in data["data"]:
            print(f" - {paper['title']} ({paper['venue']}, {paper['year']})")
        return ""

    if 'abstract' not in found_paper or found_paper['abstract'] is None:
        print(f"Warning: no abstract for {found_paper['title']}")
        return ""
    abstract = found_paper['abstract'].strip()
    if abstract == "":
        print(f"Warning: empty abstract for {found_paper['title']}")
    return abstract


def get_papers(name, year, fetch_abstracts):
    cnt = 0
    new_cnt = 0
    confs = NAME_MAP[name]
    if confs is str or isinstance(confs, tuple):
        confs = [confs]

    for conf in confs:
        conf_type = "conf"
        if len(conf) == 2:
            conf_name, conf = conf
        elif len(conf) == 3:
            conf_name, conf, conf_type = conf
        filename = f"{conf}{year}.html"
        if "{YEAR}" in conf:
            conf = conf.format(YEAR=year)
            filename = f"{conf}.html"
        try:
            r = requests.get(f"https://dblp.org/db/{conf_type}/{conf_name}/{filename}")
            if r.status_code == 404:
                logger.warning(f"Failed to obtain papers at {name}-{year}")
                continue
            assert r.status_code == 200

            html = BeautifulSoup(r.text, 'html.parser')
            paper_htmls = html.find_all("li", {'class': ["inproceedings", "article"]})
            for paper_html in paper_htmls:
                title = paper_html.find('span', {'class': 'title'}).text
                authors = [x.text for x in paper_html.find_all('span', {'itemprop': 'author'})]
                # insert the entry only if the paper does not exist
                if not paper_exist(name, year, title, authors):
                    abstract = ""
                    if fetch_abstracts:
                        abstract = get_abstract(title, year)
                        time.sleep(S2_REQUESTS_PER_SECOND)
                    save_paper(name, year, title, authors, abstract)
                    new_cnt += 1
                elif fetch_abstracts and not paper_has_abstract(name, year, title):
                    abstract = get_abstract(title, year)
                    if abstract:
                        update_paper(name, year, title, abstract)
                    time.sleep(S2_REQUESTS_PER_SECOND)
                cnt += 1
        except Exception as e:
            logger.warning(f"Failed to obtain papers at {name}-{year}")
            logger.exception(e)

    logger.debug(f"Found {new_cnt} new papers ({cnt} total) at {name}-{year}...")


def build_db(fetch_abstracts):
    for conf in CONFERENCES:
        for year in range(2000, datetime.now().year+1):
            get_papers(conf, year, fetch_abstracts)
