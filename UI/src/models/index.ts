export interface User {
  id: string;
  email: string;
  name: string;
  provider: string;
  organization: string;
  username:string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  name: string;
  email: string;
  password: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
}
