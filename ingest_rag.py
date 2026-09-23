import os
import psycopg2
from google import genai
from dotenv import load_dotenv
from config.database import get_db_params

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

DB_PARAMS = get_db_params()

DOCUMENTS = [
    {
        "title": "CARDI - Toxicité H2S et asphyxie racinaire du riz",
        "category": "riz",
        "content": "Symptômes: racines noires pourries, odeur d'œuf pourri (H2S), nanisme et jaunissement à 30-50 jours. Cause: enfouissement de paille fraîche non décomposée combiné à une submersion continue et apport d'urée. Traitement: drainage immédiat 3-5 jours jusqu'à fissuration superficielle, arrêt total d'urée, apport de chaux agricole si pH acide, relance avec KCl et DAP dès l'émergence des racines blanches."
    },
    {
        "title": "MAFF - Gestion post-récolte et maladies du manioc",
        "category": "manioc",
        "content": "Récolte: tubercules périssables en 24-48h (détérioration physiologique post-récolte). Si vente séchée, trancher et sécher à moins de 14% d'humidité. Sélection des boutures: tiges de 8-12 mois saines, rejeter toute tige présentant des symptômes du virus de la mosaïque du manioc (CMD - feuilles cloquées/crispées). Conservation à l'ombre max 1 mois. Reconstitution du sol avec fumier et NPK 15-15-15."
    },
    {
        "title": "CARDI - Carence en Azote et Potassium sur sols sableux (Prey Veng / Kampong Chhnang)",
        "category": "sol",
        "content": "Sur sols légers ou lessivés, le jaunissement uniforme des feuilles basses indique une carence en Azote (N). Le brunissement de la pointe des feuilles indique une carence en Potassium (K). Appliquer urée fractionnée et chlorure de potassium (KCl) après ressuyage du sol."
    }
]

def get_embedding(text: str):
    res = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text
    )
    return res.embeddings[0].values

def ingest():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    # Cleanly reset the vector table
    cur.execute("TRUNCATE rag_documents;")
    for doc in DOCUMENTS:
        emb = get_embedding(doc["content"])
        cur.execute("""
            INSERT INTO rag_documents (source_title, category, content, embedding)
            VALUES (%s, %s, %s, %s);
        """, (doc["title"], doc["category"], doc["content"], emb))
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ {len(DOCUMENTS)} fiches CARDI/MAFF vectorisées avec pgvector.")

if __name__ == "__main__":
    ingest()
