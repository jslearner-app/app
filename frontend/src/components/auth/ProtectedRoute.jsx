import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { FullScreenLoader } from "@/components/common/FullScreenLoader";

export const ProtectedRoute = ({ children }) => {
  const { user } = useAuth();
  if (user === null) return <FullScreenLoader label="Loading workspace..." />;
  if (user === false) return <Navigate to="/login" replace />;
  return children;
};
