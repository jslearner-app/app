import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FullScreenLoader } from "@/components/common/FullScreenLoader";
import { GOOGLE_STATE_KEY, googleRedirectUri } from "@/components/auth/GoogleButton";

export const AuthCallback = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    const expected = sessionStorage.getItem(GOOGLE_STATE_KEY);
    sessionStorage.removeItem(GOOGLE_STATE_KEY);
    const fail = (msg) => {
      toast.error(msg);
      navigate("/login", { replace: true });
    };
    if (params.get("error")) return fail("Google sign-in was cancelled.");
    if (!params.get("code") || !expected || params.get("state") !== expected) return fail("Google sign-in expired. Please try again.");
    api
      .post("/auth/google", { code: params.get("code"), redirect_uri: googleRedirectUri() })
      .then(({ data }) => {
        setUser(data);
        navigate("/dashboard", { replace: true });
      })
      .catch((e) => fail(errMsg(e)));
  }, [params, navigate, setUser]);

  return <FullScreenLoader label="Signing you in..." />;
};
