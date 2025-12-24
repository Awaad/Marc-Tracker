import { useState } from "react";
import { useAuth } from "../state/auth";

export default function Login() {
  const login = useAuth((s) => s.login);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);

  return (
    <div style={{ padding: 24, maxWidth: 420 }}>
      <h2>Login</h2>
      <input
        placeholder="email or username"
        value={identifier}
        onChange={(e) => setIdentifier(e.target.value)}
        style={{ width: "100%", marginBottom: 8 }}
      />
      <input
        placeholder="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        style={{ width: "100%", marginBottom: 8 }}
      />
      <button
        onClick={async () => {
          setErr(null);
          try {
            await login(identifier, password);
          } catch (e: any) {
            setErr(e.message);
          }
        }}
      >
        Login
      </button>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
