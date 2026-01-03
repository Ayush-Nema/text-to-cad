import json
import time


def load_md(md_path):
    with open(md_path, "r", encoding="utf-8") as fp:
        return fp.read()


def timeit(func):
    def wrapper(state):
        start = time.time()
        result = func(state)
        end = time.time()
        print(f"{func.__name__} took {end - start:.2f} seconds.")
        return result

    return wrapper


def parse_json(ai_response):
    try:
        clean_str = ai_response.content.strip('`json\n').strip('`')
        args = json.loads(clean_str)
    except json.JSONDecodeError:
        args = {}
    return args
