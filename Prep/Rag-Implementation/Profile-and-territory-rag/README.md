# Prep: RAG Knowledge Base and Ingestion to OpenSearch Serverless (AOSS)

This folder contains:
- hcp-knowledge-base[precall].txt — the RAG context document used by agents
- ingest_knowledge_to_opensearch.py — a helper script to embed and index the document into AOSS

Use this README to create/update the RAG doc and ingest it into your OpenSearch Serverless vector index.

## 1) Prerequisites

- AWS account and CLI configured (credentials in ~/.aws/credentials)
- OpenSearch Serverless (AOSS) collection for Vector Search (must exist before ingest)
- Bedrock access to an embedding model (e.g., amazon.titan-embed-text-v2)
- Python 3.10+ on Windows


## 2) Create or Verify AOSS Collection (one-time)

Note: You can also automate with CloudFormation.

If you do not already have a Vector Search collection:

PowerShell:
```powershell
# Create a Vector Search collection
aws opensearchserverless create-collection `
  --name sc-rag `
  --type VECTORSEARCH `
  --region us-east-1

# Allow encryption/network (example permissive policies — tighten for prod)
aws opensearchserverless create-security-policy `
  --name sc-rag-encrypt `
  --type encryption `
  --policy '{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/sc-rag\"]}],\"AWSOwnedKey\":true}' `
  --region us-east-1

aws opensearchserverless create-security-policy `
  --name sc-rag-network `
  --type network `
  --policy '{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/sc-rag\"]}],\"AllowFromPublic\":true}' `
  --region us-east-1

# Grant data access to your IAM principal (replace ARN)
aws opensearchserverless create-access-policy `
  --name sc-rag-access `
  --type data `
  --policy '[{"Description":"Dev access","Rules":[{"ResourceType":"index","Resource":["index/sc-rag/*"],"Permission":["aoss:*"]},{"ResourceType":"collection","Resource":["collection/sc-rag"],"Permission":["aoss:*"]}],"Principal":["arn:aws:iam::<ACCOUNT_ID>:user/<USER_OR_ROLE>"]}]' `
  --region us-east-1
```

After the collection is ACTIVE, note its endpoint (AOSS console → Collections → sc-rag).

## 3) Configure and Run Ingestion

- Update endpoint and index name, then run the script from this folder.

PowerShell:
```powershell
# Navigate to the prep folder
cd "LS salse copilot\sales-copilot\Pre-Call-Agents-Agentcore\prep"

# (Optional) Create and activate a virtual environment
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install boto3 opensearch-py

# Set environment values (replace with your actual endpoint and index)
$env:SC_AOSS_ENDPOINT = "https://<your-aoss-endpoint>"
$env:SC_HCP_AOSS_INDEX = "sc_hcp_kb"
$env:SALES_COPILOT_BEDROCK_EMBED_MODEL = "amazon.titan-embed-text-v2:0"
$env:AWS_REGION = "us-east-1"

# Run ingestion with local file path
python ".\ingest_knowledge_to_opensearch.py" `
  --file ".\hcp-knowledge-base[precall].txt" `
  --endpoint $env:SC_AOSS_ENDPOINT `
  --index $env:SC_HCP_AOSS_INDEX `
  --model-id $env:SALES_COPILOT_BEDROCK_EMBED_MODEL `
  --region $env:AWS_REGION
```

### 4) Store values in Parameter Store (for agent use)

Recommended SSM parameters:
- SALES_COPILOT_AOSS_ENDPOINT = your AOSS endpoint
- SC_HCP_AOSS_INDEX = sc_hcp_kb
- SALES_COPILOT_BEDROCK_EMBED_MODEL = amazon.titan-embed-text-v2:0

After setting, agents can read these via get_parameter_value.

### 5) Verify ingestion

- Run a k-NN search against the index to confirm chunks are indexed.
- Ensure index vector dimension matches the embedding model.