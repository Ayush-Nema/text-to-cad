from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from utils.utils import parse_json, load_and_format_prompt


# from rich.traceback import install
# install()


def get_dimensions(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    )

    system_prompt = load_and_format_prompt("prompts/prompt_to_dims.md")

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("messages")  # pulls messages from state automatically
    ])
    chain = prompt | llm

    # invoke the chain with current messages
    response = chain.invoke({"messages": state["messages"]})
    # parse JSON output
    args = parse_json(response)

    return {
        "dimensions": args,  # new field in state
        "messages": [AIMessage(content=str(args))]  # reducer will append this automatically
    }
