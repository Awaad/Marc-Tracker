import express from "express";
import { WebSocketServer } from "ws";
import makeWASocket, { useMultiFileAuthState } from "@whiskeysockets/baileys";

const app = express();
app.use(express.json());

const wss = new WebSocketServer({ noServer: true });
const clients = new Set<any>();

wss.on("connection", (ws) => {
  clients.add(ws);
  ws.on("close", () => clients.delete(ws));
});

function broadcast(obj: any) {
  const msg = JSON.stringify(obj);
  for (const ws of clients) {
    try { ws.send(msg); } catch {}
  }
}

const server = app.listen(8099, () => console.log("wa-bridge listening on :8099"));

server.on("upgrade", (req, socket, head) => {
  if (req.url?.startsWith("/events")) {
    wss.handleUpgrade(req, socket, head, (ws) => wss.emit("connection", ws, req));
  } else {
    socket.destroy();
  }
});

(async () => {
  // Persist auth state on disk
  const { state, saveCreds } = await useMultiFileAuthState("./auth");
  const sock = makeWASocket({ auth: state, printQRInTerminal: true });

  sock.ev.on("creds.update", saveCreds);

  // For outgoing message delivery/read-ish signals, Baileys surfaces updates here (best-effort).
  sock.ev.on("messages.update", (updates: any[]) => {
    for (const u of updates) {
      const messageId = u?.key?.id;
      const status = u?.update?.status ?? u?.update?.ack; // varies by version
      if (typeof messageId === "string" && status !== undefined) {
        broadcast({ type: "wa:update", message_id: messageId, status, ts: Date.now() });
      }
    }
  });

  app.post("/send", async (req, res) => {
    const { to, text } = req.body ?? {};
    if (!to || !text) return res.status(400).json({ error: "to,text required" });

    const jid = String(to).replace("+", "") + "@s.whatsapp.net";
    const r = await sock.sendMessage(jid, { text: String(text) });

    res.json({ message_id: r?.key?.id ?? null, raw: r });
  });
})();
