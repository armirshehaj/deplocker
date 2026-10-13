import logging
import logging.handlers

from pythonjsonlogger.json import JsonFormatter


def setup_logging() -> logging.Logger:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)

    file_handler = logging.handlers.RotatingFileHandler(
        "app/logs/app.log", maxBytes=100 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(logging.INFO)

    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    json_formatter = JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(method)s %(path)s"
        "%(status_code)s %(duration)s"
    )

    stream_handler.setFormatter(console_formatter)
    file_handler.setFormatter(json_formatter)

    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    # Under uvicorn --reload, watchfiles logs each change it detects at INFO, those
    # in app/logs/ included, so every such line would trigger another
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    return root_logger
