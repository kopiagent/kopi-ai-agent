import { useEffect, useRef } from "react";
import { api, buildWsUrl, type OfficeAgent } from "@/lib/api";

/**
 * Pixel Office — a concrete visualization of the multi-agent process.
 *
 * Each live subagent (from /api/office/state, backed by delegate_tool's
 * list_active_subagents; realtime via the `office` event channel) becomes a
 * pixel NPC that walks to a workstation matching what it's doing and leaves
 * when it completes. Parent→child agents are joined by a collaboration line.
 *
 * Renderer: Canvas 2D, pixel-crisp (nearest-neighbor, integer virtual res).
 *
 * NPC skins are pluggable. Today we ship original procedural characters
 * (varied hair/shirt/tone, keyed by agent id). To drop in real spritesheets
 * later (e.g. a Stardew-style pack or a custom mascot), extend SKINS with a
 * `sheet` image + frame meta and branch in drawChar — the office logic is skin-
 * agnostic. (Don't ship copyrighted or real-person art without rights.)
 */

// ---- virtual resolution ----------------------------------------------------
const VW = 520;
const VH = 340;

// ---- palette ---------------------------------------------------------------
const C = {
  pageBg: "#789f6b",
  pageGrassA: "#87ad72",
  pageGrassB: "#6f965e",
  wall: "#f4e7c8",
  wallShadow: "#dfc998",
  wallTrim: "#b88455",
  floorA: "#d4a766",
  floorB: "#c99655",
  floorLine: "#a9773f",
  rug: "#9d5b49",
  rugEdge: "#744235",
  rugGold: "#d2a455",
  desk: "#bf7c45",
  deskHi: "#d39b5a",
  deskEdge: "#7f4d2e",
  wood: "#a86138",
  woodLight: "#c9854d",
  woodDark: "#6e3f29",
  screenOff: "#264e60",
  screenOn: "#8bd2d6",
  metal: "#9aa7a0",
  metalDark: "#5f6867",
  plant: "#4f8f4c",
  plantLight: "#7db65b",
  plantDark: "#326f3a",
  plantPot: "#a65736",
  text: "#342819",
  sub: "#6c5b3c",
  boss: "#bc713f",
  line: "rgba(94,64,38,0.42)",
  cream: "#fff3cf",
  berry: "#b94a4c",
  sky: "#9dd3db",
  shadow: "rgba(54,32,18,0.22)",
  light: "rgba(255,229,143,0.16)",
};

// ---- original NPC skins (pluggable) ----------------------------------------
interface Skin { hair: string; shirt: string; tone: string; }
const SKINS: Skin[] = [
  { hair: "#4a3526", shirt: "#5a86c4", tone: "#f3d9b0" },
  { hair: "#1f1c1a", shirt: "#5aa469", tone: "#f0cfa0" },
  { hair: "#8a5a2b", shirt: "#c0684a", tone: "#f6ddb8" },
  { hair: "#6b3fa0", shirt: "#8a6fc0", tone: "#efd3ad" },
  { hair: "#c08a2a", shirt: "#3fa3a3", tone: "#f7e0bd" },
  { hair: "#2b2b2b", shirt: "#c94f7c", tone: "#eccaa0" },
  { hair: "#5a3a1a", shirt: "#4b6bb0", tone: "#f2d6ac" },
  { hair: "#7a7a7a", shirt: "#b0863f", tone: "#f0d2a6" },
];
function skinFor(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return h % SKINS.length;
}

// ---- status → workstation --------------------------------------------------
// (When the backend later reports the live tool, richer mapping slots in here.)
type StationType = "computer" | "bookshelf" | "whiteboard" | "server";
function stationFor(status: string): StationType {
  switch ((status || "").toLowerCase()) {
    case "reading": return "bookshelf";
    case "searching": return "bookshelf";
    case "thinking": return "whiteboard";
    case "running": return "server";
    default: return "computer"; // writing / working / active
  }
}
const VERB: Record<string, string> = {
  writing: "typing", running: "running", reading: "reading",
  searching: "searching", thinking: "thinking", waiting: "waiting", done: "done",
};

// Raw tool names ("mcp_xero_list_profit_and_loss") → the same human-phrased
// title-case label the TUI shows in its tool-call log ("Mcp Xero List Profit
// And Loss"), so the feet label matches what the user sees in chat.
function formatToolLabel(tool: string): string {
  return tool
    .replace(/[_.]+/g, " ")
    .trim()
    .split(/\s+/)
    .map((w) => (w.length ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

// station seats: fixed spots the NPC walks to
const STATIONS: Record<StationType, { x: number; y: number }[]> = {
  computer: [
    { x: 250, y: 175 }, { x: 320, y: 175 }, { x: 390, y: 175 },
    { x: 250, y: 250 }, { x: 320, y: 250 }, { x: 390, y: 250 },
  ],
  bookshelf: [{ x: 70, y: 150 }, { x: 70, y: 210 }, { x: 70, y: 270 }],
  whiteboard: [{ x: 250, y: 100 }, { x: 300, y: 100 }],
  server: [{ x: 470, y: 165 }, { x: 470, y: 235 }],
};
const ENTRANCE = { x: 500, y: 315 };

// ---- NPC model -------------------------------------------------------------
interface Npc {
  id: string;
  goal: string;
  status: string;
  tool: string;
  parentId: string | null;
  skin: number;
  station: StationType;
  seatKey: string;      // "station:index"
  x: number; y: number; // current px
  tx: number; ty: number; // target px
  facing: number;       // 1 right, -1 left
  gone: boolean;
  removeAt: number;
  bob: number;
}

export default function OfficePage() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const npcsRef = useRef<Map<string, Npc>>(new Map());
  const emptyRef = useRef(true);

  // ---- data layer: seed via REST, then realtime via /api/events WS ----
  useEffect(() => {
    let stopped = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let fallbackTimer: ReturnType<typeof setTimeout> | undefined;

    const freeSeats = (station: StationType, exceptId: string) => {
      const taken = new Set<string>();
      npcsRef.current.forEach((n) => {
        if (n.id !== exceptId && n.station === station && !n.gone) taken.add(n.seatKey);
      });
      const seats = STATIONS[station];
      for (let i = 0; i < seats.length; i++) {
        const key = `${station}:${i}`;
        if (!taken.has(key)) return { key, seat: seats[i] };
      }
      // overflow: reuse last seat
      return { key: `${station}:0`, seat: seats[0] };
    };

    // The first seed on page load/refresh reflects agents that may have been
    // running for a while already — they should appear seated immediately,
    // not replay a "walk in from the door" spawn animation. Only agents that
    // genuinely appear later (via realtime WS updates) should walk in.
    const applyAgents = (agents: OfficeAgent[], isSeed = false) => {
      const now = performance.now();
      const seen = new Set<string>();
      emptyRef.current = agents.length === 0;
      agents.forEach((a) => {
        seen.add(a.subagent_id);
        const station = stationFor(a.status);
        const existing = npcsRef.current.get(a.subagent_id);
        if (existing) {
          existing.goal = a.goal;
          existing.tool = a.tool || "";
          existing.gone = false;
          existing.removeAt = 0;
          if (existing.status !== a.status && existing.station !== station) {
            // status changed → walk to a seat in the new station
            const { key, seat } = freeSeats(station, existing.id);
            existing.station = station;
            existing.seatKey = key;
            existing.tx = seat.x;
            existing.ty = seat.y;
          }
          existing.status = a.status;
        } else {
          const { key, seat } = freeSeats(station, a.subagent_id);
          npcsRef.current.set(a.subagent_id, {
            id: a.subagent_id,
            goal: a.goal || "(task)",
            status: a.status || "running",
            tool: a.tool || "",
            parentId: a.parent_id ?? null,
            skin: skinFor(a.subagent_id),
            station,
            seatKey: key,
            x: isSeed ? seat.x : ENTRANCE.x,
            y: isSeed ? seat.y : ENTRANCE.y, // walk in from the door, unless this is the initial seed
            tx: seat.x, ty: seat.y,
            facing: -1,
            gone: false, removeAt: 0,
            bob: (skinFor(a.subagent_id) * 17) % 100,
          });
        }
      });
      npcsRef.current.forEach((npc, id) => {
        if (!seen.has(id) && !npc.gone) {
          npc.gone = true;
          npc.removeAt = now + 1600;
          npc.tx = ENTRANCE.x; npc.ty = ENTRANCE.y; // walk out
        }
      });
    };

    const seed = async () => {
      try { const s = await api.getOfficeState(); if (!stopped) applyAgents(s.agents, true); }
      catch { /* keep last frame */ }
    };
    const connect = async () => {
      if (stopped) return;
      try {
        const url = await buildWsUrl("/api/events", { channel: "office" });
        if (stopped) return;
        ws = new WebSocket(url);
        ws.addEventListener("message", (ev) => {
          try {
            const frame = JSON.parse(ev.data);
            if (frame?.method === "event" && frame.params?.type === "office.state")
              applyAgents(frame.params.payload?.agents ?? []);
          } catch { /* ignore */ }
        });
        ws.addEventListener("close", () => { if (!stopped) reconnectTimer = setTimeout(connect, 2000); });
        ws.addEventListener("error", () => { try { ws?.close(); } catch { /* noop */ } });
      } catch { if (!stopped) reconnectTimer = setTimeout(connect, 3000); }
    };
    const fallback = async () => {
      if (stopped) return;
      try { const s = await api.getOfficeState(); if (!stopped) applyAgents(s.agents); } catch { /* noop */ }
      if (!stopped) fallbackTimer = setTimeout(fallback, 8000);
    };

    void seed(); void connect(); fallbackTimer = setTimeout(fallback, 8000);
    return () => {
      stopped = true; ws?.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (fallbackTimer) clearTimeout(fallbackTimer);
    };
  }, []);

  // ---- render loop ----
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let raf = 0;

    const resize = () => {
      const parent = canvas.parentElement;
      const w = parent?.clientWidth ?? 800, h = parent?.clientHeight ?? 500;
      const dpr = Math.max(1, Math.floor(window.devicePixelRatio || 1));
      canvas.width = w * dpr; canvas.height = h * dpr;
      canvas.style.width = w + "px"; canvas.style.height = h + "px";
    };
    resize();
    window.addEventListener("resize", resize);

    // --- furniture ---
    const rect = (x: number, y: number, w: number, h: number, c: string) => { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); };
    const outlineRect = (x: number, y: number, w: number, h: number, fill: string, edge = C.woodDark, hi = "rgba(255,255,255,0.18)") => {
      rect(x, y, w, h, edge);
      rect(x + 1, y + 1, w - 2, h - 2, fill);
      rect(x + 2, y + 2, w - 4, 1, hi);
    };
    const pixelText = (text: string, x: number, y: number, size: number, color: string, align: CanvasTextAlign = "center") => {
      ctx.fillStyle = color;
      ctx.font = `bold ${size}px monospace`;
      ctx.textAlign = align;
      ctx.fillText(text, x, y);
    };
    const drawGrass = (w: number, h: number, t: number) => {
      rect(0, 0, w, h, C.pageGrassA);
      for (let y = 0; y < h; y += 18) {
        for (let x = 0; x < w; x += 18) {
          if (((x / 18 + y / 18) | 0) % 2 === 0) rect(x, y, 18, 18, C.pageGrassB);
        }
      }
      for (let i = 0; i < 70; i++) {
        const x = (i * 47 + Math.floor(t / 180)) % Math.max(1, w);
        const y = (i * 31) % Math.max(1, h);
        rect(x, y, 2, 5, i % 3 ? "#5f8f55" : "#e5c765");
      }
    };
    const drawOfficeShell = () => {
      rect(8, 8, VW - 16, VH - 12, "#6f442d");
      rect(10, VH - 7, VW - 20, 5, "rgba(31,20,13,0.28)");
      rect(13, 13, VW - 26, VH - 22, "#8f5737");
      rect(18, 18, VW - 36, VH - 32, C.wall);
      rect(18, 18, VW - 36, 10, "#fbf1d4");
      for (let x = 23; x < VW - 28; x += 22) rect(x, 31, 12, 1, C.wallShadow);
      for (let x = 34; x < VW - 28; x += 42) rect(x, 55, 18, 1, "#ead8ad");
      rect(18, 65, VW - 36, 7, C.wallTrim);
      rect(18, 72, VW - 36, 5, C.woodDark);
      rect(24, 77, VW - 48, 3, "rgba(255,255,255,0.12)");
    };
    const drawDeskWithPC = (x: number, y: number, on: boolean, t: number) => {
      rect(x - 20, y + 26, 40, 4, C.shadow);
      rect(x - 18, y + 7, 36, 13, C.deskEdge);
      rect(x - 17, y + 5, 34, 12, C.desk);
      rect(x - 16, y + 5, 32, 2, C.deskHi);
      rect(x - 16, y + 15, 32, 1, "#8e5631");
      rect(x - 14, y + 18, 3, 12, C.woodDark);
      rect(x + 11, y + 18, 3, 12, C.woodDark);
      rect(x - 12, y + 18, 1, 9, "#a96b3d");
      rect(x + 13, y + 18, 1, 9, "#a96b3d");
      rect(x - 9, y - 9, 18, 14, C.metalDark);          // monitor frame
      rect(x - 7, y - 7, 14, 10, on && Math.floor(t / 220) % 2 === 0 ? C.screenOn : C.screenOff);
      if (on) rect(x - 6, y - 6, 3, 8, "rgba(255,255,255,0.28)");
      rect(x - 5, y - 5, 3, 1, "#dff9ef");
      rect(x - 3, y + 6, 6, 3, C.metalDark);            // stand
      rect(x - 10, y + 10, 11, 2, C.metalDark);         // keyboard
      rect(x + 8, y + 9, 3, 3, "#e7d39b");             // note
      rect(x - 14, y + 9, 4, 5, "#774531");            // mug
    };
    const drawChair = (x: number, y: number) => {
      rect(x - 10, y + 18, 20, 3, C.shadow);
      outlineRect(x - 8, y + 9, 16, 10, "#855638", "#5b3424");
      rect(x - 6, y + 19, 3, 8, "#5b3424");
      rect(x + 3, y + 19, 3, 8, "#5b3424");
      rect(x - 6, y + 8, 12, 2, "#a96b45");
    };
    const drawBookshelf = (x: number, y: number) => {
      rect(x - 18, y + 52, 36, 4, C.shadow);
      rect(x - 16, y - 49, 32, 103, C.woodDark);
      rect(x - 13, y - 46, 26, 98, C.wood);
      rect(x - 11, y - 44, 22, 3, C.woodLight);
      for (let r = 0; r < 4; r++) {
        const sy = y - 40 + r * 24;
        rect(x - 11, sy, 22, 3, C.woodDark);
        for (let b = 0; b < 6; b++) rect(x - 10 + b * 4, sy - 13, 3, 13, ["#9f4646","#4f8f4c","#3f6f9c","#d0a44c","#8d5ca6","#c76d45"][(r + b) % 6]);
      }
      rect(x + 6, y + 35, 4, 7, "#f0d66c");
    };
    const drawWhiteboard = (x: number) => {
      rect(x - 35, 73, 98, 40, C.woodDark);
      rect(x - 32, 76, 92, 34, "#fff8df");
      rect(x - 22, 84, 40, 2, "#5ca0a6"); rect(x - 22, 92, 55, 2, "#b76b66"); rect(x - 22, 100, 30, 2, "#737bb0");
      rect(x + 40, 83, 8, 8, "#d9b55f");
      rect(x + 10, 102, 14, 2, "#6c8b62");
      rect(x - 32, 110, 92, 2, "#8a5b3c");
    };
    const drawServer = (x: number, y: number, t: number) => {
      rect(x - 13, y + 36, 26, 4, C.shadow);
      rect(x - 10, y - 30, 20, 66, C.metalDark);
      rect(x - 8, y - 28, 16, 2, "#b7c0b8");
      for (let i = 0; i < 6; i++) {
        rect(x - 7, y - 26 + i * 10, 14, 7, C.metal);
        rect(x + 3, y - 24 + i * 10, 2, 2, (i + Math.floor(t / 300)) % 3 === 0 ? "#6f6" : "#363");
        rect(x - 5, y - 22 + i * 10, 5, 1, "#707b77");
      }
      rect(x - 17, y + 25, 9, 2, "#5b3424");
      rect(x - 20, y + 22, 3, 8, "#5b3424");
    };
    const drawPlant = (x: number, y: number) => {
      rect(x - 6, y, 12, 9, C.plantPot); rect(x - 4, y + 6, 8, 2, "#713a28");
      rect(x - 10, y - 11, 9, 9, C.plantDark); rect(x + 1, y - 13, 10, 11, C.plant);
      rect(x - 4, y - 20, 8, 12, C.plantLight); rect(x + 5, y - 20, 5, 7, C.plantDark);
    };
    const drawCoffee = (x: number, y: number, t: number) => {
      rect(x - 11, y + 6, 22, 3, C.shadow);
      rect(x - 7, y - 10, 14, 15, C.metalDark); rect(x - 5, y - 7, 10, 7, "#c98a52"); rect(x - 4, y + 5, 8, 2, C.woodDark); rect(x + 7, y - 6, 3, 5, C.metalDark);
      const steam = Math.floor(t / 260) % 3;
      rect(x - 5, y - 18 - steam, 1, 4, "#fff4d6");
      rect(x + 1, y - 16 + steam, 1, 3, "#fff4d6");
    };
    const drawWindow = (x: number, y: number) => {
      rect(x - 3, y - 3, 76, 46, C.woodDark);
      rect(x, y, 70, 40, C.sky);
      rect(x, y + 27, 70, 13, "#77a85e");
      rect(x + 10, y + 10, 18, 4, "#fff4cf");
      rect(x + 45, y + 6, 11, 11, "#f0c95a");
      rect(x + 34, y, 3, 40, C.woodDark); rect(x, y + 19, 70, 3, C.woodDark);
      rect(x + 2, y + 2, 66, 2, "#c6edf0");
    };
    const drawWallDecor = () => {
      rect(42, 24, 54, 31, C.woodDark); rect(45, 27, 48, 25, "#f9dc99");
      rect(51, 43, 34, 5, "#8fbf68"); rect(60, 34, 9, 9, "#c94d43"); rect(70, 31, 6, 12, "#5f8f55");
      rect(111, 28, 22, 24, C.woodDark); rect(114, 31, 16, 18, "#d9f0df"); rect(119, 35, 6, 8, "#86ad64");
      rect(438, 18, 30, 36, C.woodDark); rect(441, 21, 24, 30, "#eacb74"); rect(448, 28, 10, 10, "#fff3cf");
    };
    const drawFloor = () => {
      for (let gy = 72; gy < VH - 18; gy += 18) {
        for (let gx = 18; gx < VW - 18; gx += 36) {
          rect(gx, gy, 36, 18, ((gx / 36 + gy / 18) | 0) % 2 ? C.floorA : C.floorB);
          rect(gx, gy + 17, 36, 1, C.floorLine);
          if (((gx * 7 + gy * 11) % 5) === 0) rect(gx + 7, gy + 6, 12, 1, "rgba(91,55,30,0.18)");
          if (((gx * 3 + gy * 5) % 7) === 0) rect(gx + 22, gy + 12, 9, 1, "rgba(255,238,184,0.18)");
        }
      }
      for (let gx = 18; gx < VW - 18; gx += 36) rect(gx + 35, 72, 1, VH - 90, "rgba(93,57,32,0.18)");
    };
    const drawRug = () => {
      rect(222, 154, 214, 126, C.rugEdge);
      rect(227, 159, 204, 116, C.rug);
      rect(235, 167, 188, 100, "#b9664f");
      rect(246, 178, 166, 78, C.rug);
      for (let x = 239; x < 420; x += 16) { rect(x, 164, 8, 4, C.rugGold); rect(x, 268, 8, 4, C.rugGold); }
    };
    const drawWindowLight = () => {
      ctx.fillStyle = C.light;
      ctx.beginPath();
      ctx.moveTo(368, 55);
      ctx.lineTo(444, 55);
      ctx.lineTo(480, 190);
      ctx.lineTo(318, 190);
      ctx.closePath();
      ctx.fill();
    };
    const drawStatusIcon = (x: number, y: number, status: string, tool: string) => {
      const s = (status || "").toLowerCase();
      const pulse = tool ? "#8bd2d6" : "#fff2bd";
      rect(x - 8, y - 29, 16, 12, "#5b3424");
      rect(x - 7, y - 30, 14, 12, "#fff4cc");
      if (s === "reading") {
        rect(x - 5, y - 27, 5, 7, "#6f8bbd"); rect(x, y - 27, 5, 7, "#b95b54"); rect(x, y - 27, 1, 7, "#5b3424");
      } else if (s === "searching") {
        ctx.strokeStyle = "#9b6a3e"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x - 1, y - 24, 3, 0, Math.PI * 2); ctx.stroke(); rect(x + 2, y - 21, 4, 1, "#9b6a3e");
      } else if (s === "thinking") {
        pixelText("?", x, y - 21, 9, "#8a5b3c");
      } else if (s === "running") {
        rect(x - 5, y - 26, 10, 6, C.metalDark); rect(x - 3, y - 24, 6, 2, pulse); rect(x - 1, y - 20, 2, 2, C.metalDark);
      } else {
        rect(x - 5, y - 26, 10, 7, C.metalDark); rect(x - 4, y - 25, 8, 5, pulse);
      }
    };
    const drawLabel = (x: number, y: number, top: string, bottom: string) => {
      const g = top.length > 20 ? top.slice(0, 19) + "…" : top;
      const labelW = Math.min(62, Math.max(28, g.length * 4));
      rect(x - labelW / 2 - 1, y - 42, labelW + 2, 12, "#6e3f29");
      rect(x - labelW / 2, y - 43, labelW, 12, "#fff4cc");
      rect(x - labelW / 2 + 2, y - 34, labelW - 4, 1, "#d5ad64");
      ctx.fillStyle = C.text; ctx.font = "6px monospace"; ctx.textAlign = "center";
      ctx.fillText(g, x, y - 35);
      const footTrunc = bottom.length > 22 ? bottom.slice(0, 21) + "…" : bottom;
      rect(x - Math.min(70, Math.max(30, footTrunc.length * 4)) / 2, y + 17, Math.min(70, Math.max(30, footTrunc.length * 4)), 8, "rgba(255,244,204,0.82)");
      ctx.fillStyle = C.sub; ctx.fillText(footTrunc, x, y + 23);
    };

    // --- character (procedural skin) ---
    const drawChar = (x: number, y: number, skin: Skin, t: number, moving: boolean, action: string, bobSeed: number) => {
      const walk = moving ? Math.sin(t / 90) : 0;
      const bob = moving ? Math.abs(Math.sin(t / 90)) * 1.2 : Math.sin(t / 380 + bobSeed) * 1.0;
      const by = y - bob;
      // shadow
      ctx.fillStyle = "rgba(45,28,14,0.18)"; ctx.fillRect(x - 7, y + 11, 14, 3);
      // legs
      rect(x - 4, by + 8, 3, 5 + (moving ? walk * 1.5 : 0), "#4a4a4a");
      rect(x + 1, by + 8, 3, 5 - (moving ? walk * 1.5 : 0), "#4a4a4a");
      // body/shirt
      rect(x - 6, by - 2, 12, 12, "#5d3d2d");
      rect(x - 5, by - 1, 10, 10, skin.shirt);
      rect(x - 4, by + 1, 8, 1, "rgba(255,255,255,0.22)");
      // arms — action-dependent
      if (action === "type") { const a = Math.floor(t / 120) % 2; rect(x - 7, by + 2 + a, 2, 4, skin.shirt); rect(x + 5, by + 2 + (1 - a), 2, 4, skin.shirt); }
      else if (action === "read") { rect(x - 8, by + 1, 3, 6, "#d9c9a0"); } // holding a book
      else { rect(x - 7, by + 2, 2, 5, skin.shirt); rect(x + 5, by + 2, 2, 5, skin.shirt); }
      // head + hair
      rect(x - 5, by - 12, 10, 10, "#5d3d2d");
      rect(x - 4, by - 11, 8, 8, skin.tone);
      rect(x - 4, by - 13, 8, 5, skin.hair);
      rect(x - 5, by - 10, 1, 3, skin.hair); rect(x + 4, by - 10, 1, 3, skin.hair);
      // eyes (face direction)
      ctx.fillStyle = "#333";
      const ex = action ? 0 : 0;
      rect(x - 2 + ex, by - 8, 1, 1, "#333"); rect(x + 1 + ex, by - 8, 1, 1, "#333");
      // action bubble
      if (action === "think") { ctx.fillStyle = "#fff7dc"; ctx.fillRect(x + 5, by - 16, 9, 7); ctx.fillStyle = C.sub; ctx.font = "6px monospace"; ctx.textAlign = "center"; ctx.fillText("…", x + 9, by - 11); }
      if (action === "search") { ctx.strokeStyle = "#c08f4a"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x + 8, by - 12, 3, 0, Math.PI * 2); ctx.stroke(); ctx.beginPath(); ctx.moveTo(x + 10, by - 10); ctx.lineTo(x + 12, by - 8); ctx.stroke(); }
      if (action === "read") { rect(x - 9, by - 2, 5, 6, "#5f72a8"); rect(x - 4, by - 2, 1, 6, "#e8d79d"); }
    };
    const actionFor = (status: string): string => {
      switch ((status || "").toLowerCase()) {
        case "reading": return "read";
        case "searching": return "search";
        case "thinking": return "think";
        case "writing": case "running": default: return "type";
      }
    };

    const render = (t: number) => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      const scale = Math.max(1, Math.min(w / VW, h / VH));
      const ox = (w - VW * scale) / 2, oy = (h - VH * scale) / 2;
      const dpr = Math.max(1, Math.floor(window.devicePixelRatio || 1));

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.imageSmoothingEnabled = false;
      drawGrass(w, h, t);
      ctx.setTransform(dpr * scale, 0, 0, dpr * scale, dpr * ox, dpr * oy);

      drawOfficeShell();
      drawFloor();
      drawRug();
      drawWindowLight();
      drawWindow(354, 14);
      drawWallDecor();
      // sign
      rect(149, 18, 124, 34, C.woodDark);
      rect(153, 21, 116, 28, C.boss);
      rect(158, 24, 106, 3, "#dc9961");
      pixelText("KOPI OFFICE", 211, 40, 13, C.cream);

      // furniture / stations
      drawWhiteboard(275);
      drawBookshelf(70, 210);
      drawServer(470, 200, t);
      drawPlant(496, 61); drawCoffee(160, 300, t);
      STATIONS.computer.forEach((s) => { drawChair(s.x, s.y); drawDeskWithPC(s.x, s.y, true, t); });

      const now = performance.now();
      const npcs = npcsRef.current;

      npcs.forEach((n) => {
        if (!n.parentId) return;
        const parent = npcs.get(n.parentId);
        if (!parent || parent.gone || n.gone) return;
        ctx.strokeStyle = C.line;
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(parent.x, parent.y - 4);
        ctx.lineTo(n.x, n.y - 4);
        ctx.stroke();
        ctx.setLineDash([]);
      });

      // NPCs
      const toDelete: string[] = [];
      [...npcs.values()].sort((a, b) => a.y - b.y).forEach((n) => {
        const dx = n.tx - n.x, dy = n.ty - n.y;
        const dist = Math.hypot(dx, dy);
        const moving = dist > 1.5;
        if (moving) { n.x += (dx / dist) * Math.min(1.8, dist); n.y += (dy / dist) * Math.min(1.8, dist); n.facing = dx < 0 ? -1 : 1; }
        if (n.gone && now >= n.removeAt) { toDelete.push(n.id); return; }
        const atSeat = !moving && !n.gone;
        drawChar(n.x, n.y, SKINS[n.skin], t, moving, atSeat ? actionFor(n.status) : "", n.bob);
        // label + verb (only when seated, to reduce clutter while walking)
        if (atSeat) {
          drawStatusIcon(n.x, n.y, n.status, n.tool);
          const foot = n.tool ? formatToolLabel(n.tool) : (VERB[n.status?.toLowerCase()] ?? n.status);
          drawLabel(n.x, n.y, n.goal, foot);
        }
      });
      toDelete.forEach((id) => npcs.delete(id));

      // Front-most props sit over feet to give the room a little depth.
      drawPlant(35, 300);
      rect(433, 305, 54, 7, C.shadow);
      outlineRect(434, 286, 52, 20, "#b46a40", C.woodDark, "#da9258");
      rect(441, 280, 8, 9, "#e9d082");
      rect(454, 278, 9, 11, "#7aa362");
      rect(469, 281, 8, 8, "#b94a4c");
      rect(438, 306, 4, 11, C.woodDark);
      rect(480, 306, 4, 11, C.woodDark);

      if (emptyRef.current && npcs.size === 0) {
        rect(128, VH - 36, 264, 22, C.woodDark);
        rect(132, VH - 33, 256, 18, "#fff2c8");
        rect(132, VH - 15, 256, 2, "#b8864f");
        ctx.fillStyle = C.sub; ctx.font = "8px monospace"; ctx.textAlign = "center";
        ctx.fillText("no agents running - spawn workers with delegate_task", VW / 2, VH - 21);
      }
      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);

  return (
    <div style={{ position: "absolute", inset: 0, background: C.pageBg }}>
      <canvas ref={canvasRef} style={{ display: "block", width: "100%", height: "100%", imageRendering: "pixelated" }} />
    </div>
  );
}
