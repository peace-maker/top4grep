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

CONFERENCES = ["RAID", "ESORICS", "ACSAC", "AsiaCCS", "PETS", "WWW", "IEEE EuroS&P", "NDSS", "IEEE S&P", "USENIX", "CCS"]

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

def grep(keywords):
    # TODO: currently we only grep from title and abstract, also grep from other fields in the future maybe?
    constraints = [sqlalchemy.or_(Paper.title.icontains(x), Paper.abstract.icontains(x)) for x in keywords]

    with Session() as session:
        papers = session.query(Paper).filter(*constraints).all()
    
    #check whether whether nltk tokenizer data is downloaded
    check_and_download_punkt()

    #tokenize the title and filter out the substring matches
    filter_paper = filter(lambda p: existed_in_tokens(fuzzy_match(p.title.lower() + " " + p.abstract.lower()), keywords), papers)

    # perform customized sorthing
    papers = sorted(filter_paper, key=lambda paper: paper.year + CONFERENCES.index(paper.conference)/10, reverse=True)
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
    for paper in papers:
        abstract = paper.abstract
        if paper.url:
            ansi_link = f"\033]8;;{paper.url}\033\\{paper.title}\033]8;;\033\\"
        else:
            ansi_link = paper.title
        header = f"{paper.year}: {paper.conference:8s} - {ansi_link}"
        for (k,c) in zip_longest(keywords, COLORS, fillvalue="\033[96m"):
            kre = re.compile("(" + re.escape(k) + ")", re.IGNORECASE)
            abstract = kre.sub(c + "\\1" "\033[00m", abstract)
            header = kre.sub(c + "\\1" + "\033[00m", header)
        print(header)
        if show_abstracts:
            print(abstract)
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

        papers = grep(keywords)
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
