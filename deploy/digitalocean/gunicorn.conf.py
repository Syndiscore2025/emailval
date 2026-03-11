import os


bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
workers = max(1, int(os.getenv("GUNICORN_WORKERS", "2")))
threads = 1
worker_class = "sync"
timeout = 300
graceful_timeout = 30
keepalive = 5
preload_app = False
accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = os.getenv("LOG_LEVEL", "info").lower()
