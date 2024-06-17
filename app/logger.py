import logging
import sys

from logging.handlers import RotatingFileHandler


# get logger
logger = logging.getLogger()

# create formatter
formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s")

# create handlers
stream_handler = logging.StreamHandler(sys.stdout)
file_handler = RotatingFileHandler(
    filename="/srv/logs/export.log", maxBytes=1000000, backupCount=5
)

# set formatters
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# add handlers to the logger
logger.handlers = [stream_handler, file_handler]

# Set log level
logger.setLevel(logging.INFO)
