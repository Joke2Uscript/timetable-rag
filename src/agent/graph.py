import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

sys.path.insert(0, str(Path(__file__).resolve().parent))  # lets `tools` / `db` import from anywhere
from tools import TOOLS  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """შენ ხარ უნივერსიტეტის ლექციების ცხრილის ასისტენტი.
წესები:
1. ინფორმაცია აიღე მხოლოდ ხელსაწყოებიდან (tools). საკუთარი ცოდნით არაფერი დაამატო.
2. დღეები ხელსაწყოებს გადაეცი საწყისი ფორმით: ორშაბათი, სამშაბათი, ოთხშაბათი, ხუთშაბათი, პარასკევი
   (მაგ. "ორშაბათს" -> "ორშაბათი"). დრო გადაეცი HH:MM ფორმატით.
3. თუ მომხმარებელი წინა კითხვას აგრძელებს ("და სამშაბათს?"), გამოიყენე წინა ჯგუფი/თემა საუბრიდან.
4. თუ ხელსაწყო პასუხობს, რომ ჯგუფი ან ჩანაწერი არ არსებობს, უთხარი ეს მომხმარებელს. არაფერი გამოიგონო.
5. თუ კითხვა ცხრილის გარეთაა (მაგ. გამოცდა, ლექტორი, ქულა) ან ხელსაწყოებით პასუხი ვერ მოიძებნა,
   თქვი: "ამ ინფორმაციას ცხრილში ვერ ვიპოვე". არასოდეს უპასუხო კითხვას მისალმებით.
6. უპასუხე ქართულად, მოკლედ. ლექციები ჩამოთვალე დროის მიხედვით: დრო, საგანი, ჯგუფი, აუდიტორია, ტიპი.
   თუ ხელსაწყომ რამდენიმე ჩანაწერი დააბრუნა, ჩამოთვალე ყველა; არც ერთი არ გამოტოვო.
7. მისალმებით უპასუხე მხოლოდ მაშინ, თუ შეტყობინება მხოლოდ მისალმებაა (მაგ. "გამარჯობა"), კითხვის გარეშე."""


def build_agent(model: str = MODEL):
    llm = ChatGroq(model=model, temperature=0, reasoning_effort="low").bind_tools(TOOLS)

    def agent(state: MessagesState):
        return {"messages": [llm.invoke([SystemMessage(SYSTEM_PROMPT)] + state["messages"])]}

    g = StateGraph(MessagesState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(TOOLS))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition)  # tool call -> "tools", otherwise END
    g.add_edge("tools", "agent")                       # tool result goes back to the LLM
    return g.compile(checkpointer=MemorySaver())       # memory: one thread_id = one conversation


def ask(agent, question: str, thread_id: str = "default"):
    """Returns (final answer, [(tool_name, args), ...])."""
    result = agent.invoke(
        {"messages": [("user", question)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    msgs = result["messages"]
    # only the tool calls made while answering THIS question
    last_user = max(i for i, m in enumerate(msgs) if m.type == "human")
    calls = [(c["name"], c["args"]) for m in msgs[last_user:]
             if m.type == "ai" for c in (getattr(m, "tool_calls", None) or [])]
    return msgs[-1].content, calls