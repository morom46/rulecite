"""A web page for asking rulecite questions.

    make demo        # then open http://localhost:8501

It runs on your own machine with the same models and threshold as the
evaluation. The models' and rules' locations can be changed with the
RULECITE_RULES, RULECITE_DENSE_MODEL, RULECITE_RERANKER, RULECITE_CACHE and
RULECITE_RESULTS environment variables (the tests use these to run it with tiny models).
"""

import os
from pathlib import Path

import streamlit as st

from rulecite.answer import Answerer, Draft, decide, saved_depth, saved_threshold
from rulecite.answer_eval import demo_examples
from rulecite.records import load_rules
from rulecite.search import CACHE, DENSE_MODEL, RERANKER, Searcher, load_models
from rulecite.testset import RULES

FALLBACK_EXAMPLES = [
    "What is the maximum award the ombudsman can make?",
    "What does the Consumer Duty mean by acting in good faith?",
    "What is the daily cap on interest for payday loans?",
]
RESULTS = Path(os.environ.get("RULECITE_RESULTS", "results"))


@st.cache_resource(show_spinner="Loading the rules and the two models ...")
def load() -> tuple[dict, Answerer]:
    rules = load_rules(Path(os.environ.get("RULECITE_RULES", RULES)))
    dense = os.environ.get("RULECITE_DENSE_MODEL", DENSE_MODEL)
    encoder, cross = load_models(dense, os.environ.get("RULECITE_RERANKER", RERANKER))
    searcher = Searcher(rules, encoder, cross, dense,
                        cache=Path(os.environ.get("RULECITE_CACHE", CACHE)))
    return {r.id: r for r in rules}, Answerer(searcher, depth=saved_depth())


@st.cache_data(show_spinner=False, max_entries=200)
def draft_for(question: str) -> Draft:
    return load()[1].drafts([question])[0]


def use_example(text: str) -> None:
    st.session_state.question = text


st.set_page_config(page_title="rulecite", page_icon="§", layout="centered")
st.title("rulecite")
st.write("Ask about UK financial rules in the FCA's **DISP** (complaints), **BCOBS** "
         "(banking conduct) and **PRIN** (the Principles and the Consumer Duty). The answer "
         "quotes the rule with its citation, or says that no rule in these books clearly "
         "answers the question.")

if not Path(os.environ.get("RULECITE_RULES", RULES)).exists():
    st.error("The rules have not been read yet. Run `make ingest` first.")
    st.stop()
rules, answerer = load()

with st.sidebar:
    st.header("Settings")
    chosen = saved_threshold()
    threshold = st.slider("Refusal threshold", -8.0, 8.0, float(round(chosen, 2)), 0.01,
                          help="Refuse when the best re-ranker score is below this. "
                               f"{chosen:.2f} was chosen on the dev questions.")
    show_all = st.toggle("Show what it considered", value=False)
    st.divider()
    st.caption(f"{len(rules):,} provisions · search re-ranks the top {answerer.depth} · "
               f"models: {DENSE_MODEL.split('/')[-1]} and {RERANKER.split('/')[-1]}, on the CPU.")

st.text_input("Your question", key="question",
              placeholder="e.g. How long does a firm have to answer a complaint?")
answered, refused, accuracy = demo_examples(RESULTS)
if answered:
    examples = answered + refused
    note = (" The last one is about rules outside these books, so it should be refused."
            if refused else "")
    st.caption(f"Or try one. These are questions from the test set that it gets right.{note} "
               f"Overall it gets {accuracy:.0%} of the test questions right, so expect "
               "mistakes on your own questions." if accuracy is not None else
               "Or try one of these questions that it gets right:")
else:
    examples = FALLBACK_EXAMPLES
    st.caption("Or try one:")
for i, example in enumerate(examples):
    st.button(example, key=f"example{i}", on_click=use_example, args=(example,))

question = st.session_state.get("question", "").strip()
if question:
    with st.spinner("Searching the rules ..."):
        draft = draft_for(question)
    answer = decide(draft, threshold)
    st.divider()
    if answer.refused:
        best = draft.candidates[0]
        st.warning(f"No provision in DISP, BCOBS or PRIN clearly answers this. The closest, "
                   f"{best.citation}, scored {best.score:.2f}, below the threshold of "
                   f"{threshold:.2f}.")
    for i, quote in enumerate(answer.quotes):
        rule = rules[quote.id]
        st.subheader(("Answer: " if i == 0 else "Also relevant: ") + quote.citation)
        st.caption(f"{rule.section_title} · score {quote.score:.2f}")
        st.markdown("> " + quote.text.replace("\n", " "))
        with st.expander("The whole provision"):
            st.text(rule.text)
    if show_all:
        st.divider()
        st.caption("The two best provisions after re-ranking, quoted or not:")
        for c in draft.candidates:
            st.write(f"**{c.citation}** (score {c.score:.2f}): {c.text}")
    st.caption("Quoted from the FCA Handbook. Check the full provision before relying on it. "
               "This is a study project, not legal advice.")
