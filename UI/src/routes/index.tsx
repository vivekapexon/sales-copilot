import React from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
// import Login from "../pages/Login/Login";
// import Signup from "../pages/Signup/Signup";
import MainLayout from "../layouts/MainLayout";
import PreCall from "../pages/PreCall";
import PostCall from "../pages/PostCall";
import Login from "../pages/Login/Login";
import AuthLayout from "../layouts/AuthLayout";
import SsoLogin from "../pages/Login/SsoLogin";
// import Users from "../pages/Users/Users";

// Protected Route Component
function ProtectedRoute() {
  const { user } = useAuth();

  // if (isLoading) {
  //   return (
  //     <div className="min-h-screen flex items-center justify-center">
  //       <div className="h-8 w-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
  //     </div>
  //   );
  // }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

// Public Route Component
function PublicRoute() {
  const { user } = useAuth();
  return !user ? <Outlet /> : <Navigate to="/" />;
}

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route element={<PublicRoute />}>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<Login />} />
          {/* <Route path="/signup" element={<Signup />} /> */}
        </Route>
        <Route path="/sso-login" element={<SsoLogin />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          {/* <Route path="/" element={<DashboardPage />} /> */}
          <Route path="/" element={<PreCall />} />
          <Route path="/pre-call" element={<PreCall />} />
          <Route path="/post-call" element={<PostCall />} />
          {/* <Route path="/pre-call" element={<Dashboard />} />
          <Route path="/post-call" element={<Users />} /> */}
        </Route>
      </Route>
    </Routes>
  );
};

export default AppRoutes;
