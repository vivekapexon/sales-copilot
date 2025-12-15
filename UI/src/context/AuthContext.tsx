import React from "react";
import type { User } from "../models";

interface AuthContextType {
  user: User | null;
  setUser: React.Dispatch<React.SetStateAction<User | null>>;
  isLoading: boolean;
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>;
  chatHistoryList: any[];
  error: string | null;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  signInWithSSO: (provider: string) => void;
  signInWithPassword: (username: string, password: string) => Promise<void>;
  signOut: () => void;
  setChatHistoryList: (list: any[]) => void;
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = React.useState<User | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [chatHistoryList, setChatHistoryList] = React.useState<any[]>([]);

  React.useEffect(() => {
    // Check for existing session
    const storedUser = localStorage.getItem("auth_user");
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setIsLoading(false);
  }, []);

  const signInWithSSO = async (provider: string) => {
    setIsLoading(false);
    const domain = import.meta.env.VITE_USE_COGNITO_DOMAIN;
    const clientId = import.meta.env.VITE_USE_COGNITO_CLIENT_ID;
    const redirectUri = import.meta.env.VITE_USE_COGNITO_REDIRECT_URI;
    const scope = import.meta.env.VITE_USE_COGNITO_SCOPE;

    if (!domain || !clientId || !redirectUri || !scope) {
      console.log("Missing environment variables for Cognito configuration");
      setIsLoading(false);
      console.log(provider);
      return;
    }

    const loginUrl = `${domain}/oauth2/authorize?response_type=code&client_id=${clientId}&redirect_uri=${encodeURIComponent(
      redirectUri
    )}&scope=${encodeURIComponent(scope)}`;
    window.location.href = loginUrl;
  };

  const signInWithPassword = async (username: string, password: string) => {
    setIsLoading(false);
    // Simulate password authentication
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Simple demo account validation
    if (username === "demo" && password === "demo") {
      const mockUser: User = {
        id: `demo-${Date.now()}`,
        email: "demo@aiagent.hub",
        name: "Demo User",
        provider: "demo",
        organization: "demo-org",
        username: "demo.user",
      };

      setUser(mockUser);
      localStorage.setItem("auth_user", JSON.stringify(mockUser));
    }

    setIsLoading(false);
  };

  const signOut = () => {
    setUser(null);

    /** Set tokens in localstorage */
    localStorage.removeItem("access_token");
    localStorage.removeItem("id_token");
    localStorage.removeItem("refresh_token");

    /** Set user info in localstorage */
    localStorage.removeItem("auth_user");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        setUser,
        isLoading,
        setIsLoading,
        chatHistoryList,
        error,
        setError,
        signInWithSSO,
        signInWithPassword,
        signOut,
        setChatHistoryList,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = React.useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
