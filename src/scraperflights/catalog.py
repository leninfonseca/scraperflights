"""A candidate catalog is distinct from executable adapters and approved sellers."""
import json
from importlib.resources import files


def sources(category=None, method=None, status=None):
    data = json.loads(files('scraperflights').joinpath('sources.json').read_text(encoding='utf-8'))
    return [entry for entry in data if
            (category is None or entry['category'] == category) and
            (method is None or method in entry['methods']) and
            (status is None or entry['status'] == status)]
