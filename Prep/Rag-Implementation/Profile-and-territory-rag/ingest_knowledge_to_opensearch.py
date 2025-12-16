import os
from dotenv import load_dotenv
import json
import time
import boto3
from opensearchpy import OpenSearch, helpers, RequestsHttpConnection
from opensearchpy import AWSV4SignerAuth

load_dotenv(".env")
REGION = "us-east-1"
BEDROCK_MODEL_ID = os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
AOSS_ENDPOINT = "AOSS_ENDPOINT"  # Set your AOSS endpoint here
INDEX_NAME = "INDEX_NAME"  # Set your index name here
VECTOR_DIM = int(os.getenv("VECTOR_DIM", "1024"))

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

def _aoss_client():
    if not AOSS_ENDPOINT:
        raise RuntimeError("Set NL_OPENSEARCH_SERVERLESS_ENDPOINT to your AOSS collection endpoint.")
    host = AOSS_ENDPOINT.replace("https://", "").replace("http://", "")
    creds = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(creds, REGION, service="aoss")
    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
        max_retries=3,
        retry_on_timeout=True,
    )

os_client = _aoss_client()

def ensure_index(client: OpenSearch, index: str, dim: int):
    """
    Creates the index if missing with knn_vector mapping for AOSS, including advanced settings.
    """
    if client.indices.exists(index=index):
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

def embed_text(text: str) -> list[float]:
    body = {"inputText": text}
    resp = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )
    resp_body = json.loads(resp["body"].read())
    emb = resp_body.get("embedding")
    if not emb:
        raise ValueError("Embedding model returned no vector")
    return emb

def read_schema_docs(file_path: str) -> list[dict]:
    """
    Reads a text file containing the enriched schema knowledge (the long document).
    Splits into chunks or sections for better embedding granularity.
    Returns list of {"doc_id":..., "text":..., "title":...}
    """
    with open(file_path, "r", encoding="utf-8") as f:
        full_text = f.read()
    # For simplicity, split by section headers “=====” or blank lines
    sections = full_text.split("\n\n")
    docs = []
    for i, sec in enumerate(sections):
        sec = sec.strip()
        if not sec:
            continue
        doc = {
            "doc_id": f"schema_{i}",
            "title": sec[:50],  # first 50 chars as title
            "text": sec
        }
        docs.append(doc)
    return docs

def index_documents(docs: list[dict]):
    ensure_index(os_client, INDEX_NAME, VECTOR_DIM)
    actions = []
    for doc in docs:
        emb = embed_text(doc["text"])
        actions.append({
            "_index": INDEX_NAME,
            "_source": {"title": doc["title"], "text": doc["text"], "embedding": emb}
        })
        time.sleep(0.05)
    helpers.bulk(os_client, actions)
    print(f"Indexed {len(actions)} documents into {INDEX_NAME}")

def main():
    schema_file = "path_to_your_schema_knowledge.txt"  # Set your schema knowledge file path
    docs = read_schema_docs(schema_file)
    print("Docs to index:", len(docs))
    index_documents(docs)

if __name__ == "__main__":
    main()
