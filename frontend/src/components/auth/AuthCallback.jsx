import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FullScreenLoader } from "@/components/common/FullScreenLoader";

export const AuthCallback = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    const sessionId = new URLSearchParams(location.hash.slice(1)).get("session_id");
    api
      .post("/auth/google/session", { session_id: sessionId })
      .then(({ data }) => {
        setUser(data);
        navigate("/dashboard", { replace: true });
      })
      .catch((e) => {
        toast.error(errMsg(e));
        navigate("/login", { replace: true });
      });
  }, [location.hash, navigate, setUser]);

  return <FullScreenLoader label="Signing you in..." />;
};
