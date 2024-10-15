import logging

import colorlog

# color and format
logger_formatter = colorlog.ColoredFormatter(
    '[%(name)s][%(levelname)s]%(asctime)s %(log_color)s%(message)s',
    datefmt='%m-%d %H:%M')

def new_logger(name, level='DEBUG', new=True):
    # add custom level "VERBOSE"
    VERBOSE = 5
    logging.addLevelName(VERBOSE, "VERBOSE")
    logging.Logger.verbose = lambda inst, msg, *args, **kwargs: inst.log(VERBOSE, msg, *args, **kwargs)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logger_formatter)

    logger = logging.getLogger(name)
    if new: logger.handlers = []

    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    return logger
