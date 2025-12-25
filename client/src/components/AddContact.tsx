import { useState } from "react";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

type Props = {
  onCreate: (payload: any) => Promise<void>;
};

export default function AddContactDialog({ onCreate }: Props) {
  const [open, setOpen] = useState(false);
  const [platform, setPlatform] = useState("whatsapp_web");
  const [displayName, setDisplayName] = useState("");
  const [target, setTarget] = useState("");

  async function submit() {
    await onCreate({
      platform,
      target,
      display_name: displayName,
      display_number: target,
      avatar_url: null,
      platform_meta: {},
    });
    setOpen(false);
    setDisplayName("");
    setTarget("");
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Add contact</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New contact</DialogTitle>
        </DialogHeader>

        <div className="grid gap-3">
          <div className="grid gap-2">
            <Label>Platform</Label>
            <Select value={platform} onValueChange={setPlatform}>
              <SelectTrigger>
                <SelectValue placeholder="Platform" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mock">mock</SelectItem>
                <SelectItem value="signal">signal</SelectItem>
                <SelectItem value="whatsapp_web">whatsapp_web (bridge)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label>Display name</Label>
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </div>

          <div className="grid gap-2">
            <Label>Target (phone / id)</Label>
            <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="+905..." />
          </div>
        </div>

        <DialogFooter>
          <Button onClick={submit} disabled={!target || !platform}>
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
