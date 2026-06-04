import os
import logging
from config import LOG_FILE

os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def log_error(error):
    logging.error(str(error))


def log_info(message):
    logging.info(str(message))
