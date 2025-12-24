import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import Login from "./app/Login";
//import Register from "./app/Register";
import { useAuth } from "./state/auth";
import Dashboard from "./app/Dashboard";

export default function App() {
  const token = useAuth((s) => s.token);

  return (
    <BrowserRouter>
      {!token ? (
        <>
          <div className="p-4 flex gap-4">
            <Link className="underline" to="/">Login</Link>
            <Link className="underline" to="/register">Register</Link>
          </div>
          <Routes>
            <Route path="/" element={<Login />} />
            {/* <Route path="/register" element={<Register />} /> */}
          </Routes>
        </>
      ) : (
        <Dashboard />
      )}
    </BrowserRouter>
  );
}
