"""
Creation of Cadquery knowledge base
"""

from pathlib import Path
from typing import List

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm


class CadQueryKnowledgeBase:
    """
    Handles ingestion and retrieval of CadQuery documentation and examples
    for RAG-assisted code generation.
    """

    VECTOR_DB_DIR = "./chroma_cadquery"
    COLLECTION_NAME = "cadquery_knowledge"

    def __init__(self):
        embedding = OpenAIEmbeddings(model="text-embedding-3-large")

        self.vectordb = Chroma(
            collection_name=self.COLLECTION_NAME,
            embedding_function=embedding,
            persist_directory=self.VECTOR_DB_DIR,
        )

    @staticmethod
    def infer_concept_from_code(code: str) -> str:
        # todo: [LATER] get the concept name from LLM
        code = code.lower()
        if "thread" in code:
            return "thread"
        if "fillet" in code:
            return "fillet"
        if "hole" in code:
            return "hole"
        if "extrude" in code:
            return "extrude"
        return "general"

    @staticmethod
    def infer_concepts_from_instructions(instructions: List[str]) -> List[str]:
        # todo: [LATER] get the concept name from LLM
        text = " ".join(instructions).lower()
        concepts = []

        for key in ["thread", "fillet", "hole", "extrude"]:
            if key in text:
                concepts.append(key)

        return concepts or ["general"]

    def ingest_examples(self, examples_dir: str) -> None:
        documents: List[Document] = []

        all_file_paths = list(Path(examples_dir).rglob("*.py"))
        for file_path in tqdm(all_file_paths, total=len(all_file_paths), desc="Loading tutorial examples"):
            content = file_path.read_text()
            chunks = content.split("\n\n")

            for i, chunk in enumerate(chunks):
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "source": "example",
                            "file": file_path.name,
                            "chunk_id": f"{file_path.name}::chunk_{i}",
                            "concept": self.infer_concept_from_code(chunk),
                        },
                    )
                )

        if documents:
            self.vectordb.add_documents(documents)
            print(f"✓ Ingested {len(documents)} example chunks")

    def ingest_docs(self, pdf_path: str) -> None:
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
        )

        docs = splitter.split_documents(pages)

        for i, doc in tqdm(enumerate(docs), total=len(docs), desc="Loading info from Cadquery official PDF doc"):
            doc.metadata.update({
                "source": "docs",
                "file": Path(pdf_path).name,
                "chunk_id": f"docs::chunk_{i}",
            })

        if docs:
            self.vectordb.add_documents(docs)
            print(f"✓ Ingested {len(docs)} documentation chunks")

    def retrieve(self, design_instructions: List[str], k_docs: int = 2, k_examples: int = 2) \
            -> dict[str, List[Document]]:
        """Retrieve relevant docs and examples."""
        query = " ".join(design_instructions)

        docs = self.vectordb.similarity_search(
            query=query,
            k=k_docs,
            filter={"source": "docs"},
        )

        examples = self.vectordb.similarity_search(
            query=query,
            k=k_examples,
            filter={"source": "example"},
        )

        return {"docs": docs, "examples": examples}

    @staticmethod
    def format_context(retrieved: dict[str, List[Document]]) -> str:
        """Format retrieved documents into a single context string."""
        sections: List[str] = []

        if retrieved.get("docs"):
            sections.append("=== CADQUERY API REFERENCE ===")
            sections.extend(doc.page_content for doc in retrieved["docs"])

        if retrieved.get("examples"):
            sections.append("\n=== CADQUERY EXAMPLE(S) ===")
            sections.extend(doc.page_content for doc in retrieved["examples"])

        return "\n\n".join(sections)

    def delete_database(self, delete_files: bool = False) -> None:
        """Completely clears the Chroma collection."""
        try:
            self.vectordb.delete_collection()
        except AttributeError:
            print("Warning: Chroma does not support delete_collection().")
        except Exception as e:
            print("Warning: failed to delete collection contents:", e)

        if delete_files:
            db_path = Path(self.VECTOR_DB_DIR)
            if db_path.exists():
                for item in db_path.iterdir():
                    if item.is_dir():
                        for sub in item.iterdir():
                            sub.unlink()
                        item.rmdir()
                    else:
                        item.unlink()
                db_path.rmdir()

        print("CadQuery knowledge base cleared.")

    def get_stats(self) -> dict:
        """Get statistics about the knowledge base."""
        total_docs = self.vectordb._collection.count()
        return {"total_documents": total_docs}


def setup_or_initialize_kb(examples_dir: str, pdf_path: str, force_reingest: bool = False) -> CadQueryKnowledgeBase:
    """
    Initialize and optionally populate the knowledge base. If `force_reingest`=True: delete existing DB and reingest
    data.
    Returns initialized CadQueryKnowledgeBase
    """
    kb = CadQueryKnowledgeBase()

    # Check if DB already exists
    stats = kb.get_stats()

    if force_reingest or stats["total_documents"] == 0:
        print("Ingesting knowledge base...")

        if force_reingest:
            kb.delete_database(delete_files=True)
            kb = CadQueryKnowledgeBase()  # Reinitialize

        kb.ingest_examples(examples_dir)
        kb.ingest_docs(pdf_path)

        stats = kb.get_stats()
        print(f"Knowledge base ready with {stats['total_documents']} documents")
    else:
        print(f"Using existing knowledge base with {stats['total_documents']} documents")

    return kb
