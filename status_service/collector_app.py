"""Private Cloud Scheduler entry point for the external status collector."""

from flask import Flask

from .collector import main

app = Flask(__name__)


@app.post("/collect")
def collect():
    main()
    return "", 204
