# Tools/rag_tool.py
from typing import List, Dict, Any
from strands import tool
import logging
from utilities.rag_common import os_client, embed_text, SALES_COPILOT_INDEX_NAME

@tool
def rag_lookup(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Semantic RAG over approved materials using OpenSearch Serverless vector collection.
    """
    logging.info(f"[rag_lookup] query={query!r}, top_k={top_k}")

    # 1) Embed query
    try:
        query_vec = embed_text(query)
        logging.info(f"[rag_lookup] embedding length={len(query_vec)}")
    except Exception as e:
        logging.error(f"[rag_lookup] embed_text failed: {e}")
        return [{"rag_status": "unavailable"}]

    # 2) kNN search
    body = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_vec,
                    "k": top_k
                }
            }
        }
    }

    try:
        resp = os_client.search(index=SALES_COPILOT_INDEX_NAME, body=body)
        logging.info(f"[rag_lookup] search took: {resp.get('took')} ms")
    except Exception as e:
        logging.error(f"[rag_lookup] os_client.search failed: {e}")
        return [{"rag_status": "unavailable"}]

    hits = resp.get("hits", {}).get("hits", [])
    logging.info(f"[rag_lookup] hits count: {len(hits)}")

    if not hits:
        return [{"rag_status": "unavailable"}]

    results: List[Dict[str, Any]] = []
    for h in hits:
        src = h.get("_source", {})
        results.append(
            {
                "text": src.get("text", ""),
                "score": h.get("_score"),
                "source": {
                    "uri": src.get("title", ""),
                    "type": "opensearch"
                }
            }
        )

    return results
