import time
import io
import logging
from typing import List, Dict

import boto3
from opensearchpy import helpers

from utilities.rag_common import (
    os_client,
    embed_text,
    SALES_COPILOT_INDEX_NAME,
    VECTOR_DIM
)
from utilities.get_aws_parameter_store import get_parameter_value

import PyPDF2  # Make sure PyPDF2 is installed: pip install PyPDF2

# Path will now represent a folder/prefix, NOT a file
CORPUS_PREFIX = get_parameter_value("SALES_COPILOT_APPROVED_MATERIAL_CORPUS_PATH")


def ensure_index(client, index: str, dim: int):
    """
    Creates the vector index if it's missing.
    """
    if client.indices.exists(index=index):
        logging.info(f"Index '{index}' already exists.")
        return

    body = {
        "settings": {
            "index": {"knn": True}
        },
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "title": {"type": "text"},
                "text": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dim,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil"
                    }
                }
            }
        }
    }

    client.indices.create(index=index, body=body)
    logging.info(f"Created vector index '{index}'.")


def list_pdfs_under_prefix(s3_prefix: str) -> List[str]:
    """
    Returns full S3 keys for PDFs under given folder.
    Example prefix:
        s3://bucket/folder/subfolder/
    """
    assert s3_prefix.startswith("s3://")

    without_prefix = s3_prefix.replace("s3://", "")
    bucket, prefix = without_prefix.split("/", 1)

    s3 = boto3.client("s3")
    pdf_keys = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key.lower().endswith(".pdf"):
                pdf_keys.append((bucket, key))

    logging.info(f"Found {len(pdf_keys)} PDF(s) under prefix.")
    return pdf_keys


def extract_pdf_text(bucket: str, key: str) -> str:
    """
    Reads PDF from S3 and extracts raw text.
    """
    s3 = boto3.client("s3")

    obj = s3.get_object(Bucket=bucket, Key=key)
    raw_bytes = obj["Body"].read()

    reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")

    result = "\n".join(pages_text)
    return result.strip()


def build_docs_from_text(text: str, source_name: str) -> List[Dict]:
    """
    Splits text into natural chunks separated by blank lines.
    Each chunk becomes an embedding doc entry.
    """
    chunks = [x.strip() for x in text.split("\n\n") if x.strip()]
    docs = []
    for i, chunk in enumerate(chunks):
        first_line = chunk.splitlines()[0] if chunk.splitlines() else source_name
        title = first_line.strip()[:100]

        docs.append({
            "doc_id": f"{source_name.replace('.pdf','')}_{i}",
            "title": title,
            "text": chunk
        })

    return docs


def index_documents(docs: List[Dict]):
    """
    Bulk index documents into OpenSearch.
    """
    ensure_index(os_client, SALES_COPILOT_INDEX_NAME, VECTOR_DIM)

    actions = []
    for doc in docs:
        emb = embed_text(doc["text"])
        actions.append({
            "_index": SALES_COPILOT_INDEX_NAME,
            "_source": {
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "text": doc["text"],
                "embedding": emb
            }
        })
        time.sleep(0.005)

    helpers.bulk(os_client, actions)
    logging.info(f"Indexed {len(actions)} documents.")


def main():
    """
    Main entrypoint called manually or via Lambda/batch container.
    """
    if not CORPUS_PREFIX or not CORPUS_PREFIX.startswith("s3://"):
        logging.error("CORPUS_PREFIX is invalid or missing")
        return

    pdf_refs = list_pdfs_under_prefix(CORPUS_PREFIX)
    if not pdf_refs:
        logging.error("No PDFs found to index!")
        return

    all_docs = []

    for bucket, key in pdf_refs:
        logging.info(f"Extracting text from: s3://{bucket}/{key}")
        text = extract_pdf_text(bucket, key)

        if not text.strip():
            logging.warning(f"No extractable text in: {key}")
            continue

        docs = build_docs_from_text(text, source_name=key.split("/")[-1])
        all_docs.extend(docs)

    if not all_docs:
        logging.error("No documents created after PDF parsing.")
        return

    index_documents(all_docs)


if __name__ == "__main__":
    main()
