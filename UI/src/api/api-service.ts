import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type { User } from '../models';

const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'https://6pexfv4ru7.execute-api.us-east-1.amazonaws.com',
});

// Request interceptor to add bearer token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor (optional, for handling errors)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// Common API call function
export const apiCall = async (method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH', url: string, data?: any) => {
  const response = await api.request({
    method,
    url,
    data,
  });
  return response.data;
};

// Example API functions (moved to separate files)
export const getUser = async () => {
  return await apiCall('GET', '/user');
};
export const getSessions = async (agentId:string) => {
    const storedUser = localStorage.getItem("auth_user");
     
    if(storedUser){
        const user:User = JSON.parse(storedUser);
     console.log(user.username)
    const url = `sessions?user_id=${user?.username}&agent_id=${agentId}`;
    return await apiCall('GET', url);
    }
    
};
export const getSessionById = async (sessionId:string) => {
    const storedUser = localStorage.getItem("auth_user");
     
    if(storedUser){
        const user:User = JSON.parse(storedUser);
     console.log(user.username)
    const url = `sessions/${sessionId}?user_id=${user?.username}`;
    return await apiCall('GET', url);
    }
    
};
export const addMessage = async (sessionId:string,messages:any) => {
    const storedUser = localStorage.getItem("auth_user");
     
    if(storedUser){
        const user:User = JSON.parse(storedUser);
     console.log(user.username)
    const url = `sessions/${sessionId}/messages?user_id=${user?.username}`;
    return await apiCall('POST', url,messages);
    }
    
};

export const createMessage = async (sessionId:string,prompt:string,agentId:string,role:string='user') => {
    const storedUser = localStorage.getItem("auth_user");
     
    if(storedUser){
        const user:User = JSON.parse(storedUser);
     console.log(user.username)
     const payload = {
        user_id:user?.username,
        session_id:sessionId,
        agent_id: agentId,
        title:prompt,
        role:role
     }
    const url = `/sessions?user_id=${user?.username}`;
    return await apiCall('POST', url,payload);
    }
    
};
