#!/usr/bin/env python3
import asyncio
from typing import List

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from operator import itemgetter

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.storage import LocalFileStore
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.load import dumps, loads

# --- Paths to persisted stores ---
CHROMA_DIR = "chroma_db"
DOC_STORE_DIR = "doc_store"
ID_KEY = "doc_id"

# --- Setup retriever ---
vectorstore = Chroma(
    collection_name="summaries",
    embedding_function=OpenAIEmbeddings(),
    persist_directory=CHROMA_DIR,
)

store = LocalFileStore(DOC_STORE_DIR)

retriever = MultiVectorRetriever(
    vectorstore=vectorstore,
    byte_store=store,
    id_key=ID_KEY,
)

# --- Generate query variations ---
template = """You are an AI language model assistant. 
Generate five different versions of the given user question 
to retrieve relevant documents from a vector database. 
Separate them by newlines. 
Original question: {question}"""

prompt_perspectives = ChatPromptTemplate.from_template(template)

generate_queries = (
    prompt_perspectives
    | ChatOpenAI(temperature=0, model="gpt-4o-mini")
    | StrOutputParser()
    | (lambda x: x.split("\n"))
)

# --- Utilities ---
def multi_query_retrieve(question: str, retriever_obj, doc_store, max_queries=None):
    queries = generate_queries.invoke({"question": question})
    if question not in queries:
        queries = [question] + queries
    if max_queries:
        queries = queries[:max_queries]

    all_results = []
    for q in queries:
        results = retriever_obj.invoke(q)
        all_results.extend(results)

    # dedupe by serialized object
    seen = set()
    unique_summaries = []
    for s in all_results:
        key = dumps(s)
        if key not in seen:
            seen.add(key)
            unique_summaries.append(s)

    # resolve back to originals
    doc_ids = [s.metadata.get("doc_id") for s in unique_summaries if s.metadata.get("doc_id")]
    seen_ids, unique_ids = set(), []
    for i in doc_ids:
        if i not in seen_ids:
            seen_ids.add(i)
            unique_ids.append(i)

    originals = []
    if unique_ids:
        originals = doc_store.mget(unique_ids)
        originals = [d for d in originals if d is not None]
    if not originals:
        originals = unique_summaries
    return originals

def format_docs_with_source(docs, max_docs=3, max_chars=3000):
    out = []
    for d in docs[:max_docs]:
        src = d.metadata.get("source", d.metadata.get("doc_id", "unknown"))
        text = d.page_content or ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n...[truncated]..."
        out.append(f"Source: {src}\n{text}")
    return "\n\n".join(out)

def answer_from_docs(question: str, docs, llm, max_docs=3, max_chars=3000):
    context = format_docs_with_source(docs, max_docs=max_docs, max_chars=max_chars)
    qa_prompt = ChatPromptTemplate.from_template(
        "Answer the following question based on this context:\n\n{context}\n\nQuestion: {question}"
    )
    return (qa_prompt | llm | StrOutputParser()).invoke({"context": context, "question": question})

# --- Stage-specific retrievers ---
retriever_wiki = vectorstore.as_retriever(
    search_kwargs={"k": 5, "filter": {"source_type": "api_summary"}}
)
retriever_api = vectorstore.as_retriever(
    search_kwargs={"k": 3, "filter": {"source_type": "wiki_summary"}}
)

# --- Pipeline: wiki -> api -> synthesis ---
def wiki_then_api_pipeline(question: str,
                           doc_store=retriever.docstore,
                           wiki_retr=retriever_wiki,
                           api_retr=retriever_api,
                           llm=None):
    if llm is None:
        llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")

    # Wiki stage
    wiki_docs = multi_query_retrieve(question, wiki_retr, doc_store, max_queries=3)
    wiki_answer = answer_from_docs(question, wiki_docs, llm, max_docs=3, max_chars=100000)

    # API stage (use wiki findings to enrich query)
    combined_query = question + "\n\nWiki findings:\n" + wiki_answer
    api_docs = multi_query_retrieve(combined_query, api_retr, doc_store, max_queries=2)
    api_answer = answer_from_docs(question, api_docs, llm, max_docs=3, max_chars=100000)

    # Final synthesis
    final_context = (
        "WIKI ANSWER:\n" + wiki_answer.strip() + "\n\n"
        "API ANSWER:\n" + api_answer.strip() + "\n\n"
        "Original question:\n" + question
    )
    qa_prompt = ChatPromptTemplate.from_template(
        "Answer the following question based on this context:\n\n{context}\n\nQuestion: {question}"
    )
    final_answer = (qa_prompt | llm | StrOutputParser()).invoke(
        {"context": final_context, "question": question}
    )

    return [
        TextContent(type="text", text="WIKI:\n" + wiki_answer),
        TextContent(type="text", text="API:\n" + api_answer),
        TextContent(type="text", text="FINAL:\n" + final_answer),
    ]

# --- FastMCP server ---
mcp = FastMCP("rag-mcp-server")

@mcp.tool()
async def rag_search(query: str) -> List[TextContent]:
    """
    Run staged retrieval and return structured results.
    """
    loop = asyncio.get_event_loop()
    llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")

    final_answer = await loop.run_in_executor(
        None, lambda: wiki_then_api_pipeline(query, llm=llm)
    )
    return final_answer   # ✅ already a List[TextContent]

@mcp.tool()
async def hello(name: str) -> str:
    """Simple test tool."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    asyncio.run(mcp.run())
