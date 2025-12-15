// API endpoint from environment variable or default
// const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT || 'https://cz4nknxebz2pvetjcag2r7gqva0bpkqy.lambda-url.us-east-1.on.aws/';

import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from "@aws-sdk/client-bedrock-agentcore"; // ES Modules import
import { config } from "./config";




export const getPromptResult=async (input_text:string,moduleName:string)=>{
const client = new BedrockAgentCoreClient(config);

const obj:any={
      precall:import.meta.env.VITE_SALES_PRE_CALL_ENDPOINT,
      postcall:import.meta.env.VITE_SALES_POST_CALL_ENDPOINT
    }
      const keyName = moduleName.replaceAll('-','');
      const arnUrl = obj[keyName]


let sessionId = localStorage.getItem('sessionId');
// if(!sessionId||!sessionId.length){
//   sessionId = generateSessionId(33);
//   console.log('generating new account');
//   localStorage.setItem('sessionId',sessionId)
//   const sessiongDetails = createChatSession(obj);
//     console.log(sessiongDetails);
// }

const input = {
  runtimeSessionId: sessionId || undefined,  // Must be 33+ chars
  agentRuntimeArn: arnUrl,
  // agentRuntimeArn: import.meta.env.VITE_COMPITITVE_INTELIGENCE_ENDPOINT,
  qualifier: "DEFAULT", // Optional
  payload: JSON.stringify({prompt:input_text}) //new TextEncoder().encode(input_text), // e.g. Buffer.from(input_text) or new TextEncoder().encode(input_text)   // required
};
try{
  if(input){
    const command = new InvokeAgentRuntimeCommand(input);
const response = await client.send(command);
const apiResponse = await response.response?.transformToString();

if(apiResponse){

try {
  // parsedData = JSON.parse(respResult);
  return apiResponse.toString()
} catch (error) {
  return {message:"Error Occurred in processing request please try after sometime.",result:null}
}
}
else{
  return {message:apiResponse??"Error Occurred in processing request please try after sometime.",result:null}

}
  }
}catch (error) {
  return {message:"Error in connecting with agent please try again.",result:null}
}


}