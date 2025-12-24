import Login from "./app/Login";
import { useAuth } from "./state/auth";

export default function App() {
  const token = useAuth((s) => s.token);
  return token ? <div style={{ padding: 24 }}>Logged in</div> : <Login />;
}
