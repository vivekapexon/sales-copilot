import "./App.css";
import { BrowserRouter as Router } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import AppRoutes from "./routes";
import { StoreProvider } from "./store";
import "@cloudscape-design/global-styles/index.css";

function App() {
  return (
    <StoreProvider>
      <AuthProvider>
        <Router>
          <AppRoutes />
        </Router>
      </AuthProvider>
    </StoreProvider>
  );
}

export default App;
