# utilities/rag_indexer.py
import time
from typing import List, Dict
import logging
import boto3
from opensearchpy import OpenSearch, helpers

from utilities.rag_common import os_client, embed_text, SALES_COPILOT_INDEX_NAME, VECTOR_DIM
from utilities.get_aws_parameter_store import get_parameter_value
CORPUS_PATH = get_parameter_value("CORPUS_PATH")


def ensure_index(client: OpenSearch, index: str, dim: int):
    """
    Creates the vector index if missing, with knn_vector mapping for AOSS.
    """
    if client.indices.exists(index=index):
        logging.info(f"Index '{index}' already exists. Skipping creation.")
        return

    body = {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 128
            }
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
                        "engine": "nmslib",
                        "space_type": "cosinesimil",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 32
                        }
                    }
                }
            }
        }
    }
    client.indices.create(index=index, body=body)
    logging.info(f"Created vector index '{index}' with knn_vector mapping.")


def _read_text_from_s3(s3_uri: str) -> str:
    """
    Read the entire text file from an S3 URI like:
      s3://bucket/path/to/file.txt
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Not a valid s3 uri: {s3_uri}")

    without_prefix = s3_uri[len("s3://"):]
    bucket, key = without_prefix.split("/", 1)

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    raw = obj["Body"].read()
    return raw.decode("utf-8")


def _read_text_local(path: str) -> str:
    """
    Read a local text file.
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_corpus_docs(path: str) -> List[Dict]:
    """
    Reads corpus from S3 or local and splits it into sections separated by blank lines.
    Returns list of {"doc_id":..., "title":..., "text":...}.
    """
    if path.startswith("s3://"):
        logging.info(f"Reading corpus from S3: {path}")
        full_text = _read_text_from_s3(path)
    else:
        logging.info(f"Reading corpus from local file: {path}")
        full_text = _read_text_local(path)

    sections = full_text.split("\n\n")
    docs: List[Dict] = []
    for i, sec in enumerate(sections):
        sec = sec.strip()
        if not sec:
            continue

        first_line = sec.splitlines()[0].strip()
        title = first_line if first_line else sec[:60]

        doc = {
            "doc_id": f"approved_{i}",
            "title": title,
            "text": sec
        }
        docs.append(doc)

    return docs


def index_documents(docs: List[Dict]):
    ensure_index(os_client, SALES_COPILOT_INDEX_NAME, VECTOR_DIM)#type:ignore

    actions = []
    for doc in docs:
        emb = embed_text(doc["text"])
        actions.append({
            "_index": SALES_COPILOT_INDEX_NAME,
            # IMPORTANT: do NOT set _id, let AOSS generate it
            "_source": {
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "text": doc["text"],
                "embedding": emb
            }
        })
        # optional tiny sleep
        time.sleep(0.01)

    helpers.bulk(os_client, actions)
    logging.info(f"Indexed {len(actions)} documents into '{SALES_COPILOT_INDEX_NAME}'.")


def main():
    docs = read_corpus_docs(CORPUS_PATH)#type:ignore
    logging.info("Docs to index:", len(docs))
    if not docs:
        logging.warning("No documents found in corpus. Please check CORPUS_PATH.")
        return

    index_documents(docs)


if __name__ == "__main__":
    main()
