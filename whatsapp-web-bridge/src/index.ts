import express from "express";
import { WebSocketServer } from "ws";
import makeWASocket, { useMultiFileAuthState,  DisconnectReason,
  fetchLatestBaileysVersion } from "@whiskeysockets/baileys";
import QRCode from "qrcode";


const app = express();
app.use(express.json());

const wss = new WebSocketServer({ noServer: true });
const clients = new Set<any>();

const presenceByJid = new Map<string, any>();


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


app.get("/", (_req, res) => {
  res.type("text/plain").send("OK. Use GET /qr, POST /send, WS /events");
});



const server = app.listen(8099, () => console.log("wa-bridge listening on :8099"));

server.on("upgrade", (req, socket, head) => {
  if (req.url?.startsWith("/events")) {
    wss.handleUpgrade(req, socket, head, (ws) => wss.emit("connection", ws, req));
  } else {
    socket.destroy();
  }
});

let sock: ReturnType<typeof makeWASocket> | null = null;
let isOpen = false;
let lastQr: string | null = null;

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState("./auth");
  const { version } = await fetchLatestBaileysVersion();

  // assign to global (no shadowing)
  sock = makeWASocket({ auth: state, version });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (u: any) => {
    if (u.qr) {
      lastQr = u.qr;
      console.log("QR updated. Open http://localhost:8099/qr.png");
    }

    if (u.connection === "open") {
      isOpen = true;
      console.log("connection open");
    }

    if (u.connection === "close") {
      isOpen = false;
      const statusCode = (u.lastDisconnect?.error as any)?.output?.statusCode;
      console.log("connection closed:", statusCode);

      if (statusCode === DisconnectReason.loggedOut) {
        console.log("Logged out. Delete ./auth and relink.");
        return;
      }

      setTimeout(() => startSock().catch(console.error), 1500);
    }
  });

  sock.ev.on("presence.update", (u: any) => {
  // u.id is jid, u.presences contains device presence objects
  try {
    presenceByJid.set(String(u.id), u);
    broadcast({ type: "wa:presence", jid: String(u.id), raw: u, ts: Date.now() });
  } catch {}
});


  sock.ev.on("messages.update", (updates: any[]) => {
    for (const u of updates) {
      const messageId = u?.key?.id;
      const status = u?.update?.status ?? u?.update?.ack;
      if (typeof messageId === "string" && status !== undefined) {
        broadcast({ type: "wa:update", message_id: messageId, status, ts: Date.now() });
      }
    }
  });
}

// Register routes ONCE (outside startSock)
app.post("/send", async (req, res) => {
  const { to, message } = req.body ?? {};  // Changed from text to message
  if (!to || !message) return res.status(400).json({ error: "to and message required" });

  if (!sock || !isOpen) return res.status(503).json({ error: "wa socket not connected" });

  const jid = String(to).replace("+", "") + "@s.whatsapp.net";
  
  try {
    let r;
    
    // Handle different message types
    if (typeof message === 'string') {
      // Backward compatibility: plain text
      r = await sock.sendMessage(jid, { text: String(message) });
    } else if (message.delete) {
      // Delete message
      r = await sock.sendMessage(jid, {
        delete: {
          ...message.delete,
          remoteJid: jid
        }
      });
    } else if (message.react) {
      // Reaction message
      r = await sock.sendMessage(jid, {
        react: {
          ...message.react,
          key: {
            ...message.react.key,
            remoteJid: jid
          }
        }
      });
    } else {
      // Default to sending as-is (for other message types)
      r = await sock.sendMessage(jid, message);
    }

    res.json({ message_id: r?.key?.id ?? null, raw: r });
  } catch (error: any) {
    console.error("Error sending message:", error);
    res.status(500).json({ error: error?.message ?? "Failed to send message" });
  }
});



app.get("/qr", (_req, res) => {
  res.json({ qr: lastQr });
});

app.get("/qr.png", async (_req, res) => {
  if (!lastQr) return res.status(404).send("No QR yet");
  const png = await QRCode.toBuffer(lastQr);
  res.type("image/png").send(png);
});

app.get("/presence", async (req, res) => {
  const to = String(req.query.to ?? "");
  if (!to) return res.status(400).json({ error: "to required" });
  if (!sock || !isOpen) return res.status(503).json({ error: "wa socket not connected" });

  const jid = to.replace("+", "") + "@s.whatsapp.net";

  try {
    // ask WA for presence updates
    await sock.presenceSubscribe(jid);

    const raw = presenceByJid.get(jid) ?? null;
    return res.json({ jid, raw });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message ?? "presence failed" });
  }
});


app.get("/profile", async (req, res) => {
  const to = String(req.query.to ?? "");
  if (!to) return res.status(400).json({ error: "to required" });

  if (!sock || !isOpen) return res.status(503).json({ error: "wa socket not connected" });

  const jid = to.replace("+", "") + "@s.whatsapp.net";

  try {
    const avatar_url = await sock.profilePictureUrl(jid, "image").catch(() => null);

    // try to fetch "status/about" (may be limited by Baileys / WhatsApp)
    // Many setups don't expose "about" reliably; keep as null.
    const status_text = null;

    // display_name is not reliably available for arbitrary JIDs unless you track contacts/messages.
    const display_name = null;

    const payload = { jid, avatar_url, display_name, status_text };
    console.log("[bridge] /profile", payload); 
    return res.json(payload);
  } catch (e: any) {
    console.error("[bridge] /profile error", e?.message ?? e);
    return res.status(500).json({ error: "profile lookup failed" });
  }
});


startSock().catch(console.error);