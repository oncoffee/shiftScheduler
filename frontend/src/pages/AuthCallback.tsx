import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export function AuthCallback() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = window.location.hash.substring(1);
    const params = new URLSearchParams(hash);

    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");

    if (accessToken && refreshToken) {
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("refresh_token", refreshToken);

      window.history.replaceState(null, "", window.location.pathname);

      setTimeout(() => {
        window.location.href = "/";
      }, 100);
    } else {
      setError("Authentication failed. No tokens received.");
    }
  }, [navigate]);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-destructive">
            Authentication Failed
          </h1>
          <p className="text-muted-foreground mt-2">{error}</p>
          <button
            onClick={() => navigate("/login")}
            className="mt-4 text-primary underline"
          >
            Return to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-muted-foreground">Completing sign in...</p>
      </div>
    </div>
  );
}
