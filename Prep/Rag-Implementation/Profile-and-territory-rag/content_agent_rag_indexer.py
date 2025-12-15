import os
import io
import json
import time
import logging
from typing import List, Dict

import boto3
from opensearchpy import (
    OpenSearch,
    RequestsHttpConnection,
    AWSV4SignerAuth,
    helpers,
)

import PyPDF2  # pip install PyPDF2

# ---------------------------------------------------------------------
# AWS PARAMETER STORE HELPER
# ---------------------------------------------------------------------

def get_parameter_value(parameter_name: str):
    """
    Fetch a parameter value from AWS SSM Parameter Store.
    """
    try:
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response["Parameter"]["Value"]
    except Exception as e:
        logging.error(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None


# ---------------------------------------------------------------------
# GLOBAL CONFIG
# ---------------------------------------------------------------------

REGION = "us-east-1"

SALES_COPILOT_BEDROCK_EMBED_MODEL = get_parameter_value(
    "SALES_COPILOT_BEDROCK_EMBED_MODEL"
)
SALES_COPILOT_AOSS_ENDPOINT = get_parameter_value(
    "SALES_COPILOT_AOSS_ENDPOINT"
)
SALES_COPILOT_INDEX_NAME = get_parameter_value(
    "SALES_COPILOT_INDEX_NAME"
)

CORPUS_PREFIX = get_parameter_value(
    "SALES_COPILOT_APPROVED_MATERIAL_CORPUS_PATH"
)

VECTOR_DIM = 1024

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------
# BEDROCK EMBEDDING CLIENT
# ---------------------------------------------------------------------

bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def embed_text(text: str) -> List[float]:
    """
    Generate embeddings using Amazon Bedrock.
    """
    body = {"inputText": text}

    response = bedrock.invoke_model(
        modelId=SALES_COPILOT_BEDROCK_EMBED_MODEL,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )

    response_body = json.loads(response["body"].read())
    embedding = response_body.get("embedding")

    if not embedding:
        raise ValueError("Embedding model returned no vector")

    return embedding


# ---------------------------------------------------------------------
# OPENSEARCH SERVERLESS CLIENT
# ---------------------------------------------------------------------

def create_aoss_client() -> OpenSearch:
    """
    Initialize OpenSearch Serverless client using IAM SigV4.
    """
    if not SALES_COPILOT_AOSS_ENDPOINT:
        raise RuntimeError("SALES_COPILOT_AOSS_ENDPOINT is not set")

    host = SALES_COPILOT_AOSS_ENDPOINT.replace(
        "https://", ""
    ).replace(
        "http://", ""
    )

    session = boto3.Session()
    credentials = session.get_credentials()

    auth = AWSV4SignerAuth(
        credentials,
        REGION,
        service="aoss",
    )

    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
        max_retries=3,
        retry_on_timeout=True,
    )

    logging.info(f"Using AOSS endpoint: {SALES_COPILOT_AOSS_ENDPOINT}")
    logging.info(f"Using index name:    {SALES_COPILOT_INDEX_NAME}")

    return client


os_client = create_aoss_client()

# ---------------------------------------------------------------------
# INDEX MANAGEMENT
# ---------------------------------------------------------------------

def ensure_index(client: OpenSearch, index: str, dim: int):
    """
    Create vector index if it does not exist.
    """
    if client.indices.exists(index=index):
        logging.info(f"Index '{index}' already exists")
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
                        "space_type": "cosinesimil",
                    },
                },
            }
        },
    }

    client.indices.create(index=index, body=body)
    logging.info(f"Created vector index '{index}'")


# ---------------------------------------------------------------------
# S3 + PDF PROCESSING
# ---------------------------------------------------------------------

def list_pdfs_under_prefix(s3_prefix: str) -> List[tuple]:
    """
    List all PDFs under an S3 prefix.
    """
    assert s3_prefix.startswith("s3://")

    path = s3_prefix.replace("s3://", "")
    bucket, prefix = path.split("/", 1)

    s3 = boto3.client("s3")
    pdf_keys = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key.lower().endswith(".pdf"):
                pdf_keys.append((bucket, key))

    logging.info(f"Found {len(pdf_keys)} PDF(s)")
    return pdf_keys


def extract_pdf_text(bucket: str, key: str) -> str:
    """
    Extract raw text from a PDF stored in S3.
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

    return "\n".join(pages_text).strip()


def build_docs_from_text(text: str, source_name: str) -> List[Dict]:
    """
    Split document text into chunks for embedding.
    """
    chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
    docs = []

    for i, chunk in enumerate(chunks):
        first_line = chunk.splitlines()[0] if chunk else source_name
        title = first_line[:100]

        docs.append({
            "doc_id": f"{source_name.replace('.pdf', '')}_{i}",
            "title": title,
            "text": chunk,
        })

    return docs


# ---------------------------------------------------------------------
# INDEXING
# ---------------------------------------------------------------------

def index_documents(docs: List[Dict]):
    """
    Bulk index documents into OpenSearch.
    """
    ensure_index(os_client, SALES_COPILOT_INDEX_NAME, VECTOR_DIM)#type:ignore

    actions = []

    for doc in docs:
        embedding = embed_text(doc["text"])

        actions.append({
            "_index": SALES_COPILOT_INDEX_NAME,
            "_source": {
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "text": doc["text"],
                "embedding": embedding,
            },
        })

        time.sleep(0.005)  # throttle Bedrock calls

    helpers.bulk(os_client, actions)
    logging.info(f"Indexed {len(actions)} documents")


# ---------------------------------------------------------------------
# MAIN ENTRYPOINT
# ---------------------------------------------------------------------

def main():
    if not CORPUS_PREFIX or not CORPUS_PREFIX.startswith("s3://"):
        logging.error("Invalid or missing CORPUS_PREFIX")
        return

    pdf_refs = list_pdfs_under_prefix(CORPUS_PREFIX)
    if not pdf_refs:
        logging.error("No PDFs found to index")
        return

    all_docs = []

    for bucket, key in pdf_refs:
        logging.info(f"Processing s3://{bucket}/{key}")

        text = extract_pdf_text(bucket, key)
        if not text:
            logging.warning(f"No extractable text in {key}")
            continue

        docs = build_docs_from_text(
            text=text,
            source_name=os.path.basename(key),
        )
        all_docs.extend(docs)

    if not all_docs:
        logging.error("No documents generated from PDFs")
        return

    index_documents(all_docs)


if __name__ == "__main__":
    main()
