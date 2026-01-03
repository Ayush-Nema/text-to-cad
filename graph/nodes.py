import json

from graph.data_models import DesignInstructions
from graph.tools import retrieve_cadquery_context
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI


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
def get_dimensions(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    )

    system_prompt = load_md("app/prompts/prompt_to_dims.md")

    messages = [{"role": "system", "content": system_prompt}]
    messages += state["messages"]

    response = llm.invoke(input=messages)

    # Parse JSON output from LLM
    args = parse_json(response)

    print("Exiting `get_dimensions` node")
    return {
        **state,
        "dimensions": args,
        "messages": state["messages"] + [AIMessage(content=str(args))]
    }


# ==========================================
# NODE: Validate JSON
# ==========================================
def validate_dimensions(state):
    # todo: add more validation logics here
    # todo: ask LLM whether these dims looks realistic or not. extract dims if present in the prompt else generate
    data = state.get("dimensions", {})

    if "object_type" not in data:
        state["validation_status"] = "invalid"
        state["messages"] += [AIMessage(content="Missing object_type")]
        return state

    state["validation_status"] = "valid"
    return state


# ==========================================
# NODE: CAD generator placeholder
# ==========================================
def get_design_instructions(state):
    """
    """
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    ).with_structured_output(DesignInstructions)

    system_prompt = load_md("app/prompts/design_instructions.md")
    messages = [{"role": "system", "content": system_prompt}]
    messages += state["messages"]

    # Invoke LLM — returns a DesignInstructions object, NOT a string
    design_obj: DesignInstructions = llm.invoke(messages)

    # Update the state
    state["design_instructions"] = design_obj.design_instructions
    state["object_name"] = design_obj.object_name
    state["object_summary"] = design_obj.summary

    return {
        **state,
        "messages": state["messages"] + [AIMessage(content=design_obj.model_dump_json())],
    }


def generate_cad_program(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0,
    )
    # llm_with_tools = llm.bind_tools([retrieve_cadquery_context])
    docs_and_exs = retrieve_cadquery_context(state["design_instructions"])

    system_prompt = load_md("app/prompts/cad_generation.md")
    prompt = system_prompt.format(
        docs_and_exs=docs_and_exs,
        dimensions=state["dimensions"],
        design_instructions="\n".join(
            f"{i + 1}. {step}"
            for i, step in enumerate(state["design_instructions"])
        ),
    )

    response = llm.invoke([{"role": "system", "content": prompt}])

    return {
        **state,
        "cadquery_program": response.content.strip(),
    }


# ==========================================
# NODE: Validate CAD program
# ==========================================
def validate_program(state):
    data = state.get("cadquery_program")

    if data:
        state["program_validation_status"] = "valid"
    else:
        state["program_validation_status"] = "invalid"

    return state
