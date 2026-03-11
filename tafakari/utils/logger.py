import logging

def get_logger(name):
    """
    Returns a logger instance for the given name, prefixed with 'tafakari.'
    to ensure it uses the custom logging configuration.
    """
    logger_name = f"tafakari.{name}"
    return logging.getLogger(logger_name)
