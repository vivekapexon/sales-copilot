import { fetchAuthSession } from 'aws-amplify/auth';

const AWS_REGION = import.meta.env.NEXT_PUBLIC_AWS_REGION || 'us-east-1';


// Agent runtime ARN mapping
const AGENT_RUNTIME_ARNS: Record<string, string> = {
  'data_onboarding': import.meta.env.NEXT_PUBLIC_DATA_ONBOARDING_RUNTIME_ARN || '',
  'literature_analysis': import.meta.env.NEXT_PUBLIC_LITERATURE_ANALYSIS_RUNTIME_ARN || '',
  'bioinformatics': import.meta.env.NEXT_PUBLIC_BIOINFORMATICS_RUNTIME_ARN || '',
  'hypothesis_generation': import.meta.env.NEXT_PUBLIC_HYPOTHESIS_GENERATION_RUNTIME_ARN || '',
  'causal_relationship': import.meta.env.NEXT_PUBLIC_CAUSAL_RELATIONSHIP_RUNTIME_ARN || '',
  'causal_relationship_modeling': import.meta.env.NEXT_PUBLIC_CAUSAL_RELATIONSHIP_RUNTIME_ARN || '',
  'pathway_simulation': import.meta.env.NEXT_PUBLIC_PATHWAY_SIMULATION_RUNTIME_ARN || '',
  'target_validation': import.meta.env.NEXT_PUBLIC_TARGET_VALIDATION_RUNTIME_ARN || '',
};

/**
 * Invoke AgentCore Runtime agent with JWT authentication
 * Note: When using JWT auth, we must make direct HTTPS requests, not use AWS SDK
 */
export async function invokeAgentCoreRuntime(
  agentId: string,
  prompt: string,
  sessionId: string,
  userId?: string
): Promise<string> {
  try {
    const session = await fetchAuthSession();
    const accessToken = session.tokens?.accessToken?.toString();
    
    if (!accessToken) {
      throw new Error('No authentication token available');
    }

    // Get agent-specific runtime ARN
    const runtimeArn = AGENT_RUNTIME_ARNS[agentId];
    if (!runtimeArn) {
      throw new Error(`No runtime ARN configured for agent: ${agentId}`);
    }

    // Encode the full ARN for URL
    const encodedArn = encodeURIComponent(runtimeArn);
    const endpoint = `https://bedrock-agentcore.${AWS_REGION}.amazonaws.com/runtimes/${encodedArn}/invocations`;

    const payload = JSON.stringify({ 
      prompt,
      sessionId,
      userId
    });

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: payload,
    });

    if (!response.ok) {
      throw new Error(`AgentCore invocation failed: ${response.status} ${response.statusText}`);
    }

    // Handle streaming response
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let content = '';

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        content += decoder.decode(value, { stream: true });
      }
    }

    return content;
  } catch (error) {
    console.error('AgentCore invocation error:', error);
    throw error;
  }
}

/**
 * Stream agent responses in real-time with JWT authentication
 */
export async function* streamAgentCoreRuntime(
  agentId: string,
  prompt: string,
  sessionId: string,
  userId?: string
): AsyncGenerator<string, void, unknown> {
  
  const obj:any={
      precall:import.meta.env.VITE_SALES_PRE_CALL_ENDPOINT,
      postcall:import.meta.env.VITE_SALES_POST_CALL_ENDPOINT
    }
  // Use AWS AgentCore Runtime
    const accessToken = localStorage.getItem('access_token')

  
  if (!accessToken) {
    throw new Error('No authentication token available');
  }

  const runtimeArn = obj[agentId];
  if (!runtimeArn) {
    throw new Error(`No runtime ARN configured for agent: ${agentId}`);
  }

  const encodedArn = encodeURIComponent(runtimeArn);
  const endpoint = `https://bedrock-agentcore.${AWS_REGION}.amazonaws.com/runtimes/${encodedArn}/invocations`;
  
  console.log('🚀 Starting stream:', { agentId, sessionId, userId });

  const payload = JSON.stringify({ 
    prompt,
    sessionId,
    userId
  });

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: payload,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    console.error('❌ AgentCore Error:', { status: response.status, statusText: response.statusText, body: errorBody });
    
    // If token expired, throw a specific error that can be caught and retried
    if (response.status === 403 && errorBody.includes('Ineffectual token')) {
      throw new Error('TOKEN_EXPIRED');
    }
    
    throw new Error(`AgentCore invocation failed: ${response.status} ${response.statusText} - ${errorBody}`);
  }

  const contentType = response.headers.get('content-type') || '';
  console.log('📦 Response Content-Type:', contentType);

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (reader) {
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.substring(6);
          try {
            const text = JSON.parse(data);
            if (text) yield text;
          } catch {
            if (data) yield data;
          }
        }
      }
    }
  }
  
  console.log('✅ Stream complete');
}


