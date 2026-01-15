import base64
import json
import re
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


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


def strip_markdown_code_fences(text: str) -> str:
    text = text.strip()

    # Pattern to match opening fence (``` or ```python) at the start
    opening_fence_pattern = r"^```(?:python)?\s*"
    # Pattern to match closing fence (```) at the end
    closing_fence_pattern = r"\s*```$"

    # Remove the opening fence
    text = re.sub(opening_fence_pattern, "", text, flags=re.DOTALL)
    # Remove the closing fence
    text = re.sub(closing_fence_pattern, "", text, flags=re.DOTALL)

    return text


def replace_curly_braces(t: str):
    """
    LangChain interprets single curly braces {} as template variables.
    Thus, content in prompt like raw JSON breaks the code.
    Simple fix: escape all { and } inside the prompt by doubling them
    { → {{
    } → }}
    """
    t = t.replace("{", "{{")
    t = t.replace('}', '}}')
    return t


def load_and_format_prompt(md_path):
    prompt = load_md(md_path)
    prompt = replace_curly_braces(prompt)
    return prompt
