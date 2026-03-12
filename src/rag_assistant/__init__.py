"""RAG Assistant - Norsk revisjon.

Kjernepakke for:
- Ingest av kilder (txt/pdf/docx)
- Chunking med ankere (paragraf/avsnitt/ledd/bokstav)
- Indeksering i Chroma (vektor-db)
- Retrieval (RAG) + relasjonsbasert kontekstekspansjon
- Enkel CLI + Tkinter GUI for admin av kildebibliotek

D4/D5:
- GUI-hjelp for relasjonstyper og relasjonsmaler
- Forslagspanel for semi-automatisk relasjonsbygging
- Golden questions eval (retrieval-evaluering)

Designmål:
- Vedlikeholdbar og testbar kode
- Robust parsing (best-effort): hopper over filer/ark som ikke kan leses
- Norsk revisjonsdomene (NGAAP/ISA/ISQM + lov/forskrift/dommer)
"""

__all__ = [
    "settings_profiles",
    "env_loader",
    "anchors",
    "anchor_texts",
    "anchor_tree_model",
    "document_ingestor",
    "file_ingest",
    "anchor_inventory",
    "anchor_validation",
    "kildebibliotek",
    "relation_suggestions",
    "relation_templates",
    "relation_mapping",
    "relation_io",
    "relation_diff",
    "relation_apply",
    "pilot_isa230",
    "reference_extraction",
    "relation_proposals",
    "golden_eval",
    "qa_service",
    "source_folder_import",
    "rag_index",
    "build_index",
    "rag_bridge",
    "qa_cli",
    "admin_gui",
]

__version__ = "0.1.0"
