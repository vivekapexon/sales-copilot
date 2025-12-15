import { invokeAgentCoreRuntime, streamAgentCoreRuntime } from './agentCoreService';

export const invokeAgent = async(
  agentId: string,
  prompt: string,
  sessionId: string,
  userId?: string
) => {
  try {
    return await invokeAgentCoreRuntime(agentId, prompt, sessionId, userId);
  } catch (error) {
    console.error(`Agent invocation error for ${agentId}:`, error);
    throw error;
  }
}

export const streamAgent = async(
  agentId: string,
  prompt: string,
  sessionId: string,
  userId?: string,
  onChunk?: (chunk: string) => void
) => {
  let retryCount = 0;
  const maxRetries = 1;
  while (retryCount <= maxRetries) {
    try {
      
      for await (const chunk of streamAgentCoreRuntime(agentId, prompt, sessionId, userId)) {
        onChunk?.(chunk);
      }
      return; // Success, exit
    } catch (error: any) {
      // If token expired and we haven't retried yet, try once more
      if (error.message === 'TOKEN_EXPIRED' && retryCount < maxRetries) {
        console.log('🔄 Token expired, refreshing and retrying...');
        retryCount++;
        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1s before retry
        continue;
      }
      
      console.error(`Agent streaming error for ${agentId}:`, error);
      throw error;
    }
  }
}

export const getAgentStatus = async (
  agentId: string,
  sessionId: string
) => {
  // AgentCore doesn't have a separate status endpoint
  // Return mock status for now
  console.log(agentId,sessionId)
  return {
    logs: ['Processing request...'],
    status: 'running'
  };
}

export const mapLogsToMessages = (log: string) => {
  let message = '';
  switch(log) {
    case '[TOOL] Using tool: fetch_and_store_pubmed':
      message = 'Running Tool: fetch_and_store_pubmed';
    break;
    case '[TOOL] Using tool: create_embeddings_for_s3_file':
      message = 'Running Tool: create_embeddings_for_s3_file';
    break;
    default:
      message = 'Model is processing';
  }
  return message;
}
