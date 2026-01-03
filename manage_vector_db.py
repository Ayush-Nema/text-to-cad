from pathlib import Path
from typing import List, Dict

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
    CADQUERY_VERSION = "2.x"

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
                # skip the storage of chunk if the size (whitespace stripped) is <50
                # if len(chunk.strip()) < 50:
                #     continue

                documents.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "source": "example",
                            "file": file_path.name,
                            "chunk_id": f"{file_path.name}::chunk_{i}",
                            "concept": self.infer_concept_from_code(chunk),
                            "cadquery_version": self.CADQUERY_VERSION,
                            "language": "python",
                        },
                    )
                )

        if documents:
            self.vectordb.add_documents(documents)

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
                "cadquery_version": self.CADQUERY_VERSION,
                "language": "python",
            })

        if docs:
            self.vectordb.add_documents(docs)

    def retrieve(self, design_instructions: List[str], k_docs: int = 2, k_examples: int = 2) \
            -> Dict[str, List[Document]]:

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

    def delete_database(self, delete_files: bool = False) -> None:
        """
        Completely clears the Chroma collection. Also deletes the persisted vector DB directory on disk. Use with
        caution.
        delete_files -> True : Hard reset
        """

        # delete all documents from the collection
        # Remove all documents using public API if available
        try:
            self.vectordb.delete_collection()
        except AttributeError:
            print("Warning: Chroma does not support delete_collection().")
        except Exception as e:
            print("Warning: failed to delete collection contents:", e)

        # optionally remove persisted files
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

    def debug_db_stats(self) -> None:
        print("Total documents:", self.vectordb._collection.count())

    def debug_sample(self, query: str = "extrude") -> None:
        results = self.vectordb.similarity_search(query, k=1)
        for r in results:
            print("CONTENT:\n", r.page_content)
            print("METADATA:\n", r.metadata)

    @staticmethod
    def format_context(retrieved: Dict[str, List[Document]]) -> str:
        sections: List[str] = []

        if retrieved.get("docs"):
            sections.append("### CADQUERY API REFERENCE")
            sections.extend(doc.page_content for doc in retrieved["docs"])

        if retrieved.get("examples"):
            sections.append("### CADQUERY EXAMPLE(S)")
            sections.extend(doc.page_content for doc in retrieved["examples"])

        full_context = "\n\n".join(sections)
        return full_context

    def test_retriever(self) -> None:
        design_instructions = [
            "Create a circular sketch on the XY plane.",
            "Extrude the sketch to form a shaft.",
            "Apply a helical thread along the shaft.",
        ]

        retrieved = self.retrieve(design_instructions)
        context = self.format_context(retrieved)

        print("=== RETRIEVED CONTEXT ===")
        print(context)


if __name__ == '__main__':
    from dotenv import load_dotenv

    load_dotenv()

    kb = CadQueryKnowledgeBase()

    # # Ingest CadQuery example Python files
    # kb.ingest_examples("./cadquery_info/cq_examples")
    #
    # # Ingest official CadQuery documentation PDF
    # kb.ingest_docs("./cadquery_info/cadquery-readthedocs-io-en-latest.pdf")
    #
    # # Sanity check
    # kb.debug_db_stats()
    kb.test_retriever()

    # Delete the database (USE WITH UTMOST CAUTION)
    # kb.delete_database(True)
