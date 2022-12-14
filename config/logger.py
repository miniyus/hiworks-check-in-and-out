LOGGER = {
    "version": 1,
    "formatters": {
        "simple": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },
        "info_file_handler": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "filename": "logs/log.log",
            "when": "midnight",
            "interval": 1,
            "encoding": "utf-8"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": [
            "console"
        ]
    },
    "loggers": {
        "auto-checker": {
            "level": "DEBUG",
            "handlers": [
                "info_file_handler"
            ],
            "propagate": "no"
        }
    }
}
