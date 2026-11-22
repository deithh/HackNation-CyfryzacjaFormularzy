import logging

from app.config import config

logger = logging.getLogger("app")
if config.log_level is not None:
    logger.setLevel(config.log_level)
