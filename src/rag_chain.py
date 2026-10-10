import sys

from dotenv import load_dotenv
from groq import Groq

from retriever import retrieve

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """შენ ხარ უნივერსიტეტის ლექციების ცხრილის ასისტენტი.
წესები:
1. უპასუხე მხოლოდ მოწოდებული კონტექსტიდან. საკუთარი ცოდნით არაფერი დაამატო.
2. უპასუხე ქართულად, მოკლედ და გასაგებად.
3. ლექციები ჩამოთვალე დროის მიხედვით და მიუთითე დრო, საგანი, აუდიტორია და ტიპი.
4. თუ პასუხი კონტექსტში არ არის, თქვი: "ამ ინფორმაციას ცხრილში ვერ ვიპოვე".
5. თუ მომხმარებელი მხოლოდ ესალმება, უპასუხე მისალმებით და შესთავაზე დახმარება ლექციების ცხრილთან დაკავშირებით."""


def build_prompt(question, docs):
    context = "\n".join(f"- {d['text']}" for d in docs)
    return f"კონტექსტი:\n{context}\n\nკითხვა: {question}"


def generate(system, user):
    client = Groq()  # reads GROQ_API_KEY from the environment (.env)
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        max_tokens=2000,
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content


def answer(question, k=8):
    
    filters, docs = retrieve(question, k=k)
    DAY_ORDER = ["ორშაბათი", "სამშაბათი", "ოთხშაბათი", "ხუთშაბათი", "პარასკევი", "შაბათი"]
    if "day" not in filters:
        docs = sorted(docs, key=lambda d: (DAY_ORDER.index(d["meta"]["day"]), d["meta"]["start"]))
    if not docs:
        return "ამ ინფორმაციას ცხრილში ვერ ვიპოვე", filters, docs
    text = generate(SYSTEM_PROMPT, build_prompt(question, docs))
    return text, filters, docs


if __name__ == "__main__":
    for q in ["ჯგუფი 103-ს ორშაბათს რა აქვს?",
              "სად არის ოპტიმიზაციის მეთოდები?",
              "რამდენ საათზე იწყება ფიზიკა ჯგუფ 102-ისთვის ხუთშაბათს?"]:
        text, f, docs = answer(q)
        print("\nQ:", q, "| filters:", f)
        print(text)