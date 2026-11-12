import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s: %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S",
)

logger = logging.getLogger(__name__)
