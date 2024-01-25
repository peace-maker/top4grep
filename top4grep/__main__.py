import argparse
import os
import re
from itertools import zip_longest
from pathlib import Path

import sqlalchemy
from sqlalchemy.orm import sessionmaker

from .build_db import build_db
from .db import Base, Paper
from .utils import new_logger

DB_PATH = Path(__file__).parent / "papers.db"

engine = sqlalchemy.create_engine(f'sqlite:///{DB_PATH}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

logger = new_logger("Top4Grep")

CONFERENCES = ["NDSS", "IEEE S&P", "USENIX", "CCS", "IEEE EuroS&P", "RAID",
               "ESORICS", "ACSAC", "AsiaCCS", "PETS"]


def grep(keywords):
    # TODO: currently we only grep from title and abstract, also grep from other fields in the future maybe?
    constraints = [sqlalchemy.or_(Paper.title.icontains(x), Paper.abstract.icontains(x)) for x in keywords]

    with Session() as session:
        papers = session.query(Paper).filter(*constraints).all()

    # perform customized sorthing
    papers = sorted(papers, key=lambda paper: paper.year + CONFERENCES.index(paper.conference)/10, reverse=True)
    return papers

COLORS = [
        "\033[91m", #red
    "\033[92m", # green
    "\033[93m", # yellow
    "\033[94m", # light purple
    "\033[95m", # purple
    "\033[96m" # cyan
]

def show_papers(papers, keywords):
    for paper in papers:
        abstract = paper.abstract
        header = paper.__repr__()
        for (k,c) in zip_longest(keywords, COLORS, fillvalue="\033[96m"):
            kre = re.compile("(" + re.escape(k) + ")", re.IGNORECASE)
            abstract = kre.sub(c + "\\1" "\033[00m", abstract)
            header = kre.sub(c + "\\1" + "\033[00m", header)
        print(header)
        print(abstract)
        print("")


def main():
    parser = argparse.ArgumentParser(description='Scripts to query the paper database',
                                     usage="%(prog)s [options] -k <keywords>")
    parser.add_argument('-k', type=str, help="keywords to grep, separated by ','. For example, 'linux,kernel,exploit'", default='')
    parser.add_argument('--build-db', action="store_true", help="Builds the database of conference papers")
    parser.add_argument('--abstracts', action="store_true", help="Try to load the abstracts of the papers")
    args = parser.parse_args()

    if args.k:
        assert os.path.exists(DB_PATH), f"need to build a paper database first to perform wanted queries"
        keywords = [x.strip() for x in args.k.split(',')]
        if keywords:
            logger.info("Grep based on the following keywords: %s", ', '.join(keywords))
        else:
            logger.warning("No keyword is provided. Return all the papers.")

        papers = grep(keywords)
        logger.debug(f"Found {len(papers)} papers")

        show_papers(papers,keywords)
    elif args.build_db:
        print("Building db...")
        build_db(args.abstracts)


if __name__ == "__main__":
    main()
