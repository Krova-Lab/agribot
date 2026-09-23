"""Manual check of the same retrieval path used by the Telegram bot."""

from rag_search import search_rag


if __name__ == "__main__":
    question = "Comment reconnaître et traiter la pyriculariose sur mes plants de riz ?"
    print(f"Query: {question}")
    context = search_rag(question, limit=3)
    print(context or "No eligible RAG context found.")
