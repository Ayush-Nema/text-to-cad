import json

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from graph.data_models import DesignInstructions


# from rich.traceback import install
# install()


def load_md(md_path):
    with open(md_path, "r", encoding="utf-8") as fp:
        return fp.read()


def parse_json(ai_response):
    try:
        clean_str = ai_response.content.strip('`json\n').strip('`')
        args = json.loads(clean_str)
    except json.JSONDecodeError:
        args = {}
    return args


# ==========================================
# NODE: Dimension JSON generator
# ==========================================
def generate_dimensions(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    )

    system_prompt = load_md("prompts/prompt_to_dims.md")

    messages = [{"role": "system", "content": system_prompt}]
    messages += state["messages"]

    response = llm.invoke(input=messages)

    # Parse JSON output from LLM
    args = parse_json(response)

    return {
        **state,
        "dimension_json": args,
        "messages": state["messages"] + [AIMessage(content=str(args))]
    }


# a car wheel with 250mm diameter and 5 spokes. There should a hole in the center with 15mm diameter.

# ==========================================
# NODE: Validate JSON
# ==========================================
def validate_dimensions(state):
    # todo: add more validation logics here
    data = state.get("dimension_json", {})

    if "object_type" not in data:
        state["validation_status"] = "invalid"
        state["messages"] += [AIMessage(content="Missing object_type")]
        return state

    state["validation_status"] = "valid"
    return state


# ==========================================
# NODE: Refine dimensions
# ==========================================
def refine_dimensions(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    )

    system_prompt = """
You are a CAD dimension refinement model.
Your task:
- read the entire conversation
- update dimension JSON
- return corrected JSON only
Do NOT rewrite full prompt.
    """

    messages = [{"role": "system", "content": system_prompt}]
    messages += state["messages"]

    response = llm.invoke(
        input=messages
    )

    # Parse JSON output
    try:
        clean_str = response.content.strip('`json\n').strip('`')
        args = json.loads(clean_str)
    except json.JSONDecodeError:
        args = {}

    return {
        **state,
        "dimension_json": args,
        "messages": state["messages"] + [AIMessage(content=str(args))]
    }


# ==========================================
# NODE: CAD generator placeholder
# ==========================================
def cad_generator(state):
    """
    todo: Replace with downstream CAD API logic.
    """
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    ).with_structured_output(DesignInstructions)

    system_prompt = load_md("prompts/design_instructions.md")
    messages = [{"role": "system", "content": system_prompt}]
    messages += state["messages"]

    # Invoke LLM — returns a DesignInstructions object, NOT a string
    design_obj: DesignInstructions = llm.invoke(messages)

    return {
        **state,
        # store structured data directly in state
        "design_instructions": design_obj.design_instructions,
        "object_name": design_obj.object_name,
        "object_summary": design_obj.summary,
        # optionally still append a readable message for trace/debugging
        "messages": state["messages"] + [AIMessage(content=design_obj.model_dump_json())],
    }
