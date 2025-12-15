import React from "react";
import { Outlet } from "react-router-dom";

const AuthLayout: React.FC = () => {
  return (
    // <div
    //   style={{
    //     display: "flex",
    //     justifyContent: "center",
    //     alignItems: "center",
    //     height: "100vh",
    //   }}
    // >
    //   <div
    //     style={{
    //       width: "400px",
    //       padding: "2rem",
    //       border: "1px solid #ccc",
    //       borderRadius: "8px",
    //     }}
    //   >
    <Outlet />
    // </div>
    // </div>
  );
};

export default AuthLayout;
