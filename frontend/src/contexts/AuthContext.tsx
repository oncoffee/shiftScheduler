import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";

export interface User {
  email: string;
  name: string;
  picture_url: string | null;
  role: "admin" | "editor" | "viewer";
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCurrentUser = useCallback(async (token: string): Promise<User | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        return null;
      }

      return await response.json();
    } catch {
      return null;
    }
  }, []);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    const refresh = localStorage.getItem("refresh_token");
    if (!refresh) return false;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refresh }),
      });

      if (!response.ok) {
        return false;
      }

      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);
      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem("access_token");

      if (token) {
        const userData = await fetchCurrentUser(token);
        if (userData) {
          setUser(userData);
        } else {
          const refreshed = await refreshToken();
          if (refreshed) {
            const newToken = localStorage.getItem("access_token");
            if (newToken) {
              const userData = await fetchCurrentUser(newToken);
              setUser(userData);
            }
          } else {
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
          }
        }
      }

      setIsLoading(false);
    };

    initAuth();
  }, [fetchCurrentUser, refreshToken]);

  const login = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`);
      const data = await response.json();
      window.location.href = data.auth_url;
    } catch (error) {
      console.error("Failed to initiate login:", error);
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    const token = localStorage.getItem("access_token");

    if (token) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
      } catch {
      }
    }

    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        refreshToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
