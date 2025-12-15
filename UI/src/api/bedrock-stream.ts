import {
  BedrockAgentRuntimeClient,
  InvokeAgentCommand,
} from "@aws-sdk/client-bedrock-agent-runtime";
import { config } from "./config";

const client = new BedrockAgentRuntimeClient(config);

async function run(prompt:string) {
  const input = {
    agentId: 'arn:aws:bedrock-agentcore:us-east-1:969385807621:runtime/sc_poc_supervisor_agent-M2IwWM48TC',
    agentAliasId: "6EQlKR7mTV",
    sessionId: localStorage.getItem('sessionId')?.toString(),
    inputText: prompt,
  };

  const command = new InvokeAgentCommand(input);
  const response = await client.send(command);

  // 💡 The streaming iterator is inside: response.completion
  const completion = (response as any).completion;

  if (!completion || !completion[Symbol.asyncIterator]) {
    console.log("Non-streaming response:");
    console.log(response);
    return;
  }

  console.log("Streaming response:");

  for await (const event of completion) {
    if (event.chunk) {
      const text = new TextDecoder().decode(event.chunk.bytes);
      console.log("Chunk:", text);
    }
    if (event.trace) {
      console.log("Trace event:", event.trace);
    }
  }
}



export const getPromptResult1=async (input_text:string)=>{
run(input_text);
}
