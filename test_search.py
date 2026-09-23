import os
import psycopg2
from google import genai
from dotenv import load_dotenv
from config.database import get_db_params

# Load environment variables
load_dotenv(os.path.expanduser("~/agribot/.env"))

# 1. Initialise Gemini
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Farmer's question (you can edit it)
question = "Comment reconnaître et traiter la pyriculariose sur mes plants de riz ?"
print(f"🔍 Query: '{question}'\n")

# 2. Convert the question into a vector (3072 dimensions)
print("⚙️  Vectorisation de la question via Gemini...")
res = client.models.embed_content(
    model="models/gemini-embedding-001",
    contents=question,
)
query_vector = res.embeddings[0].values

# 3. Connect to PostgreSQL
conn = psycopg2.connect(**get_db_params())
cursor = conn.cursor()

# 4. The pgvector similarity query
# The <=> operator computes cosine distance.
# 1 - distance = similarity score (1.0 = perfect match)
sql = """
SELECT source_title, content, 1 - (embedding <=> %s::vector) AS similarity
FROM rag_documents
ORDER BY embedding <=> %s::vector
LIMIT 3;
"""

print("🧠 Semantic search in PostgreSQL (top 3)...")
cursor.execute(sql, (query_vector, query_vector))
results = cursor.fetchall()

# 5. Display the results
print("\n--- 🏆 RAG RESULTS ---")
for i, row in enumerate(results, 1):
    title, content, sim = row
    print(f"\n[{i}] 📄 {title} | Similarity score: {sim:.3f}")
    # Display the first 250 characters of the chunk to verify relevance
    print(f"    « {content[:250]}... »")

cursor.close()
conn.close()
