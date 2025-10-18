import logging, os
from sys import stdout
from pathlib import Path
from functools import wraps

class SingletonLogger:
    __instance = None

    @staticmethod
    def getInstance(service_name: str = "Transcriber", log_to_file: bool = True):
        if SingletonLogger.__instance is None:
            SingletonLogger.__instance = SingletonLogger(service_name, log_to_file)
        return SingletonLogger.__instance

    def __init__(self, service_name: str, log_to_file: bool = True):
        if SingletonLogger.__instance is not None:
            raise RuntimeError("SingletonLogger already instantiated")

        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(logging.INFO)
        fmt = "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(funcName)s | %(message)s"
        formatter = logging.Formatter(fmt)

        # Console handler
        console_handler = logging.StreamHandler(stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler
        if log_to_file:
            # Use absolute log directory to ensure Docker volume works
            # log_dir = Path(os.getenv("LOG_DIR", "/app/logs"))
            log_dir = Path(__file__).resolve().parent.parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_dir / f"{service_name}.log")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

def log_exceptions(msg: str | None = None):
    _logger = SingletonLogger.getInstance().logger

    def _decorator(fn):
        @wraps(fn)
        def _wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                _logger.exception(msg or f"Error in {fn.__qualname__}: {exc}")
                raise
        return _wrapper
    return _decorator
