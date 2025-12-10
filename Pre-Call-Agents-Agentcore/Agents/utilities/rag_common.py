# utilities/rag_common.py
import os
import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from get_aws_parameter_store import get_parameter_value
import logging


REGION = "us-east-1"
SALES_COPILOT_BEDROCK_EMBED_MODEL = get_parameter_value("SALES_COPILOT_BEDROCK_EMBED_MODEL")
SALES_COPILOT_AOSS_ENDPOINT = get_parameter_value("SALES_COPILOT_AOSS_ENDPOINT")
SALES_COPILOT_INDEX_NAME = get_parameter_value("SALES_COPILOT_INDEX_NAME")
VECTOR_DIM = int("1024")

# Bedrock client (for embeddings)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def _aoss_client() -> OpenSearch:
    """
    Initialize OpenSearch Serverless (vector collection) client using IAM SigV4.
    """
    if not SALES_COPILOT_AOSS_ENDPOINT:
        raise RuntimeError("AOSS_ENDPOINT not set. Please configure it in .env")

    host = SALES_COPILOT_AOSS_ENDPOINT.replace("https://", "").replace("http://", "")

    session = boto3.Session()
    creds = session.get_credentials()
    auth = AWSV4SignerAuth(creds, REGION, service="aoss")

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
    logging.info(f"[rag_common] Using AOSS endpoint: {SALES_COPILOT_AOSS_ENDPOINT}")
    logging.info(f"[rag_common] Using index name:    {SALES_COPILOT_INDEX_NAME}")
    
    return client


os_client = _aoss_client()


def embed_text(text: str) -> list[float]:
    """
    Call Amazon Bedrock embedding model to convert text into a vector.
    """
    body = {"inputText": text}
    resp = bedrock.invoke_model(
        modelId=SALES_COPILOT_BEDROCK_EMBED_MODEL,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )
    resp_body = json.loads(resp["body"].read())
    emb = resp_body.get("embedding")
    if not emb:
        raise ValueError("Embedding model returned no vector")
    return emb
