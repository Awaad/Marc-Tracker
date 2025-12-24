import { create } from "zustand";
import { apiFetch, setToken, getToken } from "../api/http";

type AuthState = {
  token: string | null;
  setToken: (t: string | null) => void;
  login: (identifier: string, password: string) => Promise<void>;
  register: (email: string, user_name: string, password: string) => Promise<void>;
  logout: () => void;
};

export const useAuth = create<AuthState>((set) => ({
  token: getToken(),
  setToken: (t) => {
    setToken(t);
    set({ token: t });
  },
  logout: () => {
    setToken(null);
    set({ token: null });
  },
  login: async (identifier, password) => {
    const r = await apiFetch<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ identifier, password }),
    });
    setToken(r.access_token);
    set({ token: r.access_token });
  },
  register: async (email, user_name, password) => {
    const r = await apiFetch<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, user_name, password }),
    });
    setToken(r.access_token);
    set({ token: r.access_token });
  },
}));
