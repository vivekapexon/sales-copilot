import { jwtDecode } from 'jwt-decode';


interface TokenResponse {
  access_token: string;
  id_token: string;
  refresh_token: string;
}

interface UserInfo {
  email: string;
  given_name: string;
  family_name: string;
  groups?: string[];
  username?:string;
}

export const exchangeCognitoToken = async (code: string): Promise<{ user: UserInfo; tokens: TokenResponse } | null> => {
  const domain = import.meta.env.VITE_USE_COGNITO_DOMAIN;
  const clientId = import.meta.env.VITE_USE_COGNITO_CLIENT_ID;
  const redirectUri = import.meta.env.VITE_USE_COGNITO_REDIRECT_URI;
  const clientSecret = import.meta.env.VITE_USE_COGNITO_CLIENT_SECRET;

  console.log('clientSecret',clientSecret);
      console.log('clientId',clientId);
      console.log('redirectUri',redirectUri);
      console.log('domain',domain);
  if (!clientId || !clientSecret) {
    
    console.log("Missing environment variables for Cognito configuration");
    return null;
  }

  const basicAuth = btoa(`${clientId}:${clientSecret}`);
  
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
  });

  const response = await fetch(`${domain}/oauth2/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: `Basic ${basicAuth}`,
    },
    body,
  });

  const data = await response.json();
  console.log(data);

  if (!response.ok || !data.access_token) {
    throw new Error(data.error_description || "Token exchange failed");
  }

  const userInfoResp = await fetch(`${domain}/oauth2/userInfo`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${data.access_token}`,
    },
  });

  const userInfo = await userInfoResp.json();
  console.log(userInfo);

  if (!userInfoResp.ok) {
    throw new Error(userInfo.error_description || "Failed to fetch user info");
  }
  const decodedToken: any = jwtDecode(data.access_token);
  const groups = decodedToken?.['cognito:groups'] || [];

  return {
      user: {
        email: userInfo.email,
        given_name: userInfo.given_name,
        family_name: userInfo.family_name,
        username:userInfo.username,
        groups
      },
      tokens: {
        access_token: data.access_token,
        id_token: data.id_token,
        refresh_token: data.refresh_token,
      },
    };
}