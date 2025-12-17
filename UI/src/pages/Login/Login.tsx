import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { Button, Container, Box } from "@cloudscape-design/components";

export default function Login() {
  const navigate = useNavigate();
  const { user, signInWithSSO, isLoading } = useAuth();
  const [signingInWith, setSigningInWith] = useState<string | null>(null);
  // const [currentFeature, setCurrentFeature] = useState(0);

  useEffect(() => {
    if (user) {
      navigate("/");
    }
  }, [user, navigate]);

  // useEffect(() => {
  //   console.log(currentFeature);
  //   const interval = setInterval(() => {
  //     setCurrentFeature((prev) => (prev + 1) % features.length);
  //   }, 5000);
  //   return () => clearInterval(interval);
  // }, []);

  const handleSSOLogin = async () => {
    setSigningInWith("azure");
    await signInWithSSO("microsoft");
  };

  return (
    <Container
      media={{
        content: <img src="login.png" alt="placeholder" />,
        position: "side",
        width: "50%",
        height: "100%",
      }}
      className="login-container"
    >
      <Box textAlign="center" padding={"l"}>
        <img src={"aws-logo.png"} />
        <Box padding={"l"} fontSize="heading-xl" fontWeight="bold">
          Welcome to Field Intelligence Concierge
        </Box>
        <Box margin={{ top: "l" }}>
          <Button onClick={handleSSOLogin} disabled={isLoading}>
            {signingInWith === "azure" ? (
              <span className="flex items-center gap-2">
                <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Authenticating...
              </span>
            ) : (
              "Login"
            )}
          </Button>
        </Box>
      </Box>
    </Container>
  );
}
