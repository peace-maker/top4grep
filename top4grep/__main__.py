import argparse
import re
from itertools import zip_longest

import sqlalchemy
from nltk import download, word_tokenize
from nltk.data import find
from nltk.stem import PorterStemmer

from . import DB_PATH, Session
from .db import Paper
from .utils import new_logger


logger = new_logger("Top4Grep")
stemmer = PorterStemmer()

CONFERENCES = {
    "RAID": "raid",
    "ESORICS": "esorics",
    "ACSAC": "acsac",
    "AsiaCCS": "asiaccs",
    "PETS": "pets",
    "WWW": "www",
    "IEEE EuroS&P": "eurosp",
    "NDSS": "ndss",
    "IEEE S&P": "sp",
    "USENIX": "usenix",
    "CCS": "ccs",
}
CONFERENCES_REV = {v: k for k, v in CONFERENCES.items()}

# Function to check and download 'punkt' if not already available
def check_and_download_punkt():
    try:
        # Check if 'punkt' is available, this will raise a LookupError if not found
        find('tokenizers/punkt')
        #print("'punkt' tokenizer models are already installed.")
    except LookupError:
        print("'punkt' tokenizer models not found. Downloading...")
        # Download 'punkt' tokenizer models
        download('punkt')
        download('punkt_tab')
        
# trim word tokens from tokenizer to stem i.e. exploiting to exploit
def fuzzy_match(title):
    tokens = word_tokenize(title)
    return [stemmer.stem(token) for token in tokens]
    
def existed_in_tokens(tokens, keywords):
    return all(map(lambda k: stemmer.stem(k.lower()) in tokens, keywords))

def grep(keywords, include_confs='', exclude_confs=''):
    include_confs_set = set([x.strip() for x in include_confs.split(',')]) if include_confs else set(CONFERENCES.values())
    exclude_confs_set = set([x.strip() for x in exclude_confs.split(',')]) if exclude_confs else set()
    selected_confs = include_confs_set - exclude_confs_set
    for conf in selected_confs:
        if conf not in CONFERENCES_REV:
            logger.error(f"Unknown conference: {conf}. Available options: {', '.join(list(CONFERENCES.values())[::-1])}")
            return []
    selected_confs = set([CONFERENCES_REV.get(conf) for conf in selected_confs])
    logger.debug(f"Included conferences: {', '.join(selected_confs)}")
    
    # TODO: currently we only grep from title and abstract, also grep from other fields in the future maybe?
    constraints = [sqlalchemy.or_(Paper.title.icontains(x), Paper.abstract.icontains(x)) for x in keywords]
    constraints = [sqlalchemy.and_(Paper.conference.in_(selected_confs), *constraints)]

    with Session() as session:
        papers = session.query(Paper).filter(*constraints).all()
    
    #check whether whether nltk tokenizer data is downloaded
    check_and_download_punkt()

    #tokenize the title and filter out the substring matches
    filter_paper = filter(lambda p: existed_in_tokens(fuzzy_match(p.title.lower() + " " + p.abstract.lower()), keywords), papers)

    # perform customized sorthing
    papers = sorted(filter_paper, key=lambda paper: paper.year + list(CONFERENCES.keys()).index(paper.conference)/10, reverse=True)
    return papers

COLORS = [
    "\033[91m", # red
    "\033[92m", # green
    "\033[93m", # yellow
    "\033[94m", # light purple
    "\033[95m", # purple
    "\033[96m" # cyan
]

def show_papers(papers, keywords, show_abstracts=False):
    longest_conf = max([len(paper.conference) for paper in papers], default=0)
    for paper in papers:
        abstract = paper.abstract
        title = paper.title
        for (k,c) in zip_longest(keywords, COLORS, fillvalue="\033[96m"):
            kre = re.compile("(" + re.escape(k) + ")", re.IGNORECASE)
            abstract = kre.sub(c + "\\1" "\033[00m", abstract)
            title = kre.sub(c + "\\1" + "\033[00m", title)
        if paper.url:
            ansi_link = f"\033]8;;{paper.url}\033\\{title}\033]8;;\033\\"
        else:
            ansi_link = title
        header = f"{paper.year}: {paper.conference:{longest_conf}s} - {ansi_link}"
        print(header)
        if show_abstracts and abstract:
            print(abstract.strip())
            print("")

def list_missing_abstract():
    with Session() as session:
        papers = session.query(Paper).filter(Paper.abstract == "").all()
    for paper in papers:
        print(paper)

def main():
    parser = argparse.ArgumentParser(description='Scripts to query the paper database',
                                     usage="%(prog)s [options] -k <keywords>")
    parser.add_argument('-k', type=str, help="keywords to grep, separated by ','. For example, 'linux,kernel,exploit'", default='')
    parser.add_argument('-c', type=str, help="conferences to include, separated by ','. Defaults to all. Available options: " + ', '.join(list(CONFERENCES.values())[::-1]), default='')
    parser.add_argument('-cx', type=str, help="conferences to exclude, separated by ','. Defaults to none. Available options: " + ', '.join(list(CONFERENCES.values())[::-1]), default='')
    parser.add_argument('--build-db', action="store_true", help="Builds the database of conference papers")
    parser.add_argument('--missing-abstract', action="store_true", help="List the papers that do not have abstracts")
    parser.add_argument('--abstracts', action="store_true", help="Involve abstract into the database's building or query (Need Chrome for building)")
    args = parser.parse_args()

    if args.missing_abstract and not args.build_db:
        list_missing_abstract()
        return

    if args.k:
        assert DB_PATH.exists(), "need to build a paper database first to perform wanted queries"
        keywords = [x.strip() for x in args.k.split(',')]
        if keywords:
            colored_keywords = [f"{c}{k}\033[00m" for (k,c) in zip_longest(keywords, COLORS, fillvalue="\033[96m") if k and k != "\033[96m"]
            logger.info("Grep based on the following keywords: %s", ', '.join(colored_keywords))
        else:
            logger.warning("No keyword is provided. Return all the papers.")

        papers = grep(keywords, include_confs=args.c, exclude_confs=args.cx)
        logger.debug(f"Found {len(papers)} papers")

        show_papers(papers,keywords,args.abstracts)
    elif args.build_db:
        print("Building db...")
        try:
            from .build_db import build_db
        except ModuleNotFoundError:
            logger.error("Failed to import build_db. Please make sure you have the required dependencies installed. Try running 'pip install .[BUILD]'")
            return
        build_db(args.abstracts, args.missing_abstract)


if __name__ == "__main__":
    main()
