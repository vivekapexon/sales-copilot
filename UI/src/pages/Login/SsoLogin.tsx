import React from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { exchangeCognitoToken } from "../../services/SsoService";
import { Box } from "@cloudscape-design/components";
import type { User } from "../../models";

const SsoLogin = () => {
  const [searchParams] = useSearchParams();
  const auth = useAuth();
  const navigate = useNavigate();

  React.useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      auth.setError("SSO Login failed: No code Received from provider");
      auth.setIsLoading(false);
      return;
    }
    exchangeToken(code);
  }, [searchParams]);

  const exchangeToken = async (code: string) => {
    auth.setIsLoading(true);
    try {
      const result = await exchangeCognitoToken(code);
      if (result) {
        const { user, tokens } = result;

        /** Set tokens in localstorage */
        localStorage.setItem("access_token", tokens.access_token);
        localStorage.setItem("id_token", tokens.id_token);
        localStorage.setItem("refresh_token", tokens.refresh_token);

        /** Set user info in localstorage */
        const auth_user: User = {
          id: user.email,
          email: user.email,
          name: `${user.given_name} ${user.family_name}`,
          username: user.username || "",
          provider: "",
          organization: "",
        };
        localStorage.setItem("auth_user", JSON.stringify(auth_user));

        /** Update AuthContext so ProtectedRoute recognizes the user */
        auth.setUser(auth_user);

        auth.setIsLoading(false);

        navigate("/");
      }
    } catch (error: any) {
      auth.setError("SSO Login failed: " + error.message);
      auth.setIsLoading(false);
    }
  };

  return (
    <Box textAlign="center">
      <LoaderCircle size={40} className="animate-spin" />
      <Box variant={"p"}>Connecting to Sales Copilot...</Box>
    </Box>
  );
};

export default SsoLogin;
