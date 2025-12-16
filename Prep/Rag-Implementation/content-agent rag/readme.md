# RAG Index Creation for Content-Agent (Pre-Call)

This repository contains a **Retrieval-Augmented Generation (RAG) indexing pipeline** used for **Content-Agent pre-call preparation**.  
The script ingests approved PDF materials from **Amazon S3**, generates **vector embeddings using Amazon Bedrock**, and indexes them into **Amazon OpenSearch Serverless (AOSS)** for semantic retrieval.

---

## 📌 High-Level Flow

1. Read configuration securely from **AWS SSM Parameter Store**
2. List and load **PDF documents from S3**
3. Extract and chunk text from PDFs
4. Generate embeddings using **Amazon Bedrock**
5. Create / validate a **KNN vector index in OpenSearch Serverless**
6. Bulk index documents with embeddings for RAG retrieval

---

## 🧱 Architecture Overview

S3 (PDF Corpus)
↓
PDF Text Extraction (PyPDF2)
↓
Chunking Logic
↓
Amazon Bedrock (Embeddings)
↓
OpenSearch Serverless (Vector Index)



---

## ⚙️ Prerequisites

### AWS Services
- **Amazon Bedrock** (Embedding model access enabled)
- **Amazon OpenSearch Serverless (AOSS)**
- **AWS SSM Parameter Store**
- **Amazon S3**
- Proper **IAM permissions** for:
  - `bedrock:InvokeModel`
  - `aoss:*`
  - `ssm:GetParameter`
  - `s3:GetObject`, `s3:ListBucket`

### Python Version
- Python **3.9+**

---

## 📦 Dependencies

Install required packages:

```bash
pip install boto3 opensearch-py PyPDF2 requests
```

🔐 Configuration (SSM Parameters)

The script reads all runtime configuration from AWS SSM Parameter Store:

Parameter Name	Description
SALES_COPILOT_BEDROCK_EMBED_MODEL	Bedrock embedding model ID
SALES_COPILOT_AOSS_ENDPOINT	OpenSearch Serverless endpoint
SALES_COPILOT_INDEX_NAME	Vector index name
SALES_COPILOT_APPROVED_MATERIAL_CORPUS_PATH	S3 prefix containing PDFs (s3://bucket/path)

⚠️ All parameters must exist and be accessible by the execution role.

🧠 Embedding Details

Embedding Provider: Amazon Bedrock

Vector Dimension: 1024

Similarity Metric: Cosine Similarity

Index Type: knn_vector with hnsw

🗂 Index Mapping
{
  "doc_id": "keyword",
  "title": "text",
  "text": "text",
  "embedding": {
    "type": "knn_vector",
    "dimension": 1024,
    "method": {
      "name": "hnsw",
      "space_type": "cosinesimil"
    }
  }
}

📄 PDF Processing Logic

PDFs are read directly from S3

Text is extracted page-by-page using PyPDF2

Content is split into chunks using double newlines

Each chunk becomes an individual retrievable document

Document Schema

{
  "doc_id": "<pdf_name>_<chunk_index>",
  "title": "<first line of chunk>",
  "text": "<chunk content>",
  "embedding": [ ... ]
}

🚀 How to Run

Ensure AWS credentials are configured (IAM role or environment variables).

python content_agent_rag_indexer.py

🧪 Logging & Error Handling

Uses Python logging module

Gracefully handles:

Missing parameters

Empty PDFs

No documents found

Bedrock calls are throttled to avoid rate limits


🛡 Best Practices & Notes

Use approved and curated PDFs only

Keep chunk sizes moderate for better embedding quality

Re-run indexing when:

PDFs change

Embedding model changes

Index mapping updates

📌 Use Case

This pipeline is designed for:

Sales Copilot

Content-Agent Pre-Call Context Loading

RAG-based semantic search and grounding
