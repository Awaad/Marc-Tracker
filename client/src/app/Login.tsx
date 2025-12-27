import { useState } from "react";
import { useAuth } from "../state/auth";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { LyricsNowPlaying } from "../components/LyricsNowPlaying"; // adjust path

export default function Login() {
  const login = useAuth((s) => s.login);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      {/* column layout */}
      <div className="w-full max-w-md flex flex-col items-center gap-4">
        {/* centered title */}
        <h1 className="text-2xl font-semibold text-center">Marc-Tracker</h1>

        {/* login card */}
        <Card className="w-full">
          <CardHeader>
            <CardTitle>Login</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <Label>Email or Username</Label>
              <Input value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Password</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <Button
              className="w-full"
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
            </Button>
            {err && <p className="text-sm text-red-600">{err}</p>}
          </CardContent>
        </Card>

        {/* lyrics under the card */}
        <div className="w-full">
          <LyricsNowPlaying src="/lyrics/gibmirdeinfinger.txt" autoPlay loop />
        </div>
      </div>
    </div>
  );
}
