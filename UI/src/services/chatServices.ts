import axios from "axios";
import { fetchAuthSession } from 'aws-amplify/auth';

const baseUrl = import.meta.env.VITE_API_URL || '';

async function getAuthHeaders() {
  try {
    const session = await fetchAuthSession();
    const idToken = session.tokens?.idToken?.toString();
    return idToken ? { Authorization: `Bearer ${idToken}` } : {};
  } catch (error) {
    console.error('Failed to get auth token:', error);
    return {};
  }
}

export const listChatHistory = async(user_id: string, agent_id: string) => {
  if (!baseUrl) {
    console.warn('Chat API not configured, returning empty history');
    return { sessions: [] };
  }
  try {
    const url = `${baseUrl}/sessions?user_id=${user_id}&agent_id=${agent_id}`;
    console.log('Fetching chat history:');
    const headers = await getAuthHeaders();
    const response = await axios.get(url, { headers });
    console.log('Chat history response:');
    return response.data;
  } catch (error) {
    console.error('Failed to fetch chat history:', error);
    if (axios.isAxiosError(error)) {
      console.error('Response:', error.response?.data);
      console.error('Status:', error.response?.status);
    }
    return { sessions: [] };
  }
}

export const createChatSession = async(data: any) => {
  if (!baseUrl) {
    console.warn('Chat API not configured');
    return { session_id: data.session_id };
  }
  try {
    const url = `${baseUrl}/sessions?user_id=${data.user_id}`;
    const payload = {
      session_id: data.session_id,
      agent_id: data.agent_id,
      title: data.title
    }
    console.log('Creating chat session:');
    const headers = await getAuthHeaders();
    const response = await axios.post(url, payload, { headers });
    console.log('Create session response:');
    return response.data;
  } catch (error) {
    console.error('Failed to create chat session:', error);
    if (axios.isAxiosError(error)) {
      console.error('Response:', error.response?.data);
      console.error('Status:', error.response?.status);
    }
    return { session_id: data.session_id };
  }
}

export const getChatDetails = async (session_id: string, user_id: string) => {
  if (!baseUrl) {
    return { messages: [] };
  }
  try {
    const url = `${baseUrl}/sessions/${session_id}?user_id=${user_id}`;
    const headers = await getAuthHeaders();
    const response = await axios.get(url, { headers });
    return response.data;
  } catch (error) {
    console.error('Failed to get chat details:', error);
    return { messages: [] };
  }
}

export const addChatToSession = async(data: any) => {
  if (!baseUrl) {
    return { success: true };
  }
  try {
    const url = `${baseUrl}/sessions/${data.session_id}/messages`;
    const payload = {
      session_id: data.session_id,
      user_id: data.user_id,
      role: data.role,
      content: data.content
    };
    const headers = await getAuthHeaders();
    const response = await axios.post(url, payload, { headers });
    return response.data;
  } catch (error) {
    console.error('Failed to add chat message:', error);
    return { success: false };
  }
}

export const deleteChatSession = async(session_id: string, user_id: string) => {
  if (!baseUrl) {
    return { success: true };
  }
  try {
    const url = `${baseUrl}/sessions/${session_id}?user_id=${user_id}`;
    const headers = await getAuthHeaders();
    const response = await axios.delete(url, { headers });
    return response.data;
  } catch (error) {
    console.error('Failed to delete chat session:', error);
    return { success: false };
  }
}

export const updateChatSession = async(session_id: string, user_id: string, title: string) => {
  if (!baseUrl) {
    return { success: true };
  }
  try {
    const url = `${baseUrl}/sessions/${session_id}?user_id=${user_id}`;
    const headers = await getAuthHeaders();
    const response = await axios.patch(url, { title }, { headers });
    return response.data;
  } catch (error) {
    console.error('Failed to update chat session:', error);
    return { success: false };
  }
}