"""Known unverified legacy RAG entries that must not be retrieved."""

LEGACY_UNVERIFIED_TITLES = (
    "CARDI - Toxicité H2S et asphyxie racinaire du riz",
    "MAFF - Gestion post-récolte et maladies du manioc",
    "CARDI - Carence en Azote et Potassium sur sols sableux (Prey Veng / Kampong Chhnang)",
)

# The historical HF export contains off-topic material despite its agri_hf_ name.
# Keep it in storage, but do not retrieve it until its sources are audited.
EXCLUDED_HISTORICAL_PREFIX = "agri_hf_"
