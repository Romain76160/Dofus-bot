"use client";

import { useEffect, useMemo, useState } from "react";

type StateField<T = unknown> = {
  value: T | null;
  source: string;
  confidence: number;
  updated_at: string;
};

type Interactive = {
  map_id?: number | null;
  world_id?: number | null;
  gfx_id?: number | null;
  cell_id?: number | null;
  interaction_id?: number | null;
};

type GameState = {
  map_id: StateField<number>;
  player_cell: StateField<number>;
  in_fight: StateField<boolean>;
  my_turn: StateField<boolean>;
  popup_visible: StateField<boolean>;
  interactives: StateField<Interactive[]>;
  network_connected: StateField<boolean>;
  last_event: StateField<Record<string, unknown>>;
};

type NetworkCandidate = {
  semantic: string;
  path: string;
  value: number;
  confidence: number;
  reason: string;
  auto_apply: boolean;
};

type NetworkDebug = {
  messages_seen: number;
  events_in_history: number;
  last_message_type?: string | null;
  last_wire_key?: string | null;
  last_direction: string;
  candidates: NetworkCandidate[];
  applied: Record<string, number>;
  ambiguous_candidates: number;
};

type NetworkStatus = {
  enabled: boolean;
  profile_build: string;
  decoded_ingest_enabled: boolean;
  messages_seen: number;
  history_size: number;
  layouts: Record<string, unknown>;
};

type GameDataStatus = {
  path: string;
  exists: boolean;
  map_interactions_ready: boolean;
  interaction_rows: number;
  map_count: number;
  read_only: boolean;
};

type VisionStatus = {
  enabled: boolean;
  platform: string;
  window_title_query: string;
  window_found: boolean;
  capture_dependency_ready: boolean;
  opencv_dependency_ready: boolean;
  full_desktop_fallback: boolean;
  region?: {
    title: string;
    left: number;
    top: number;
    width: number;
    height: number;
  } | null;
};

const field = <T,>(value: T | null = null): StateField<T> => ({
  value,
  source: "system",
  confidence: 0,
  updated_at: "",
});

const initialState: GameState = {
  map_id: field<number>(),
  player_cell: field<number>(),
  in_fight: field(false),
  my_turn: field(false),
  popup_visible: field(false),
  interactives: field<Interactive[]>([]),
  network_connected: field(false),
  last_event: field<Record<string, unknown>>(),
};

const initialDebug: NetworkDebug = {
  messages_seen: 0,
  events_in_history: 0,
  last_direction: "unknown",
  candidates: [],
  applied: {},
  ambiguous_candidates: 0,
};

function relativeTime(iso: string): string {
  if (!iso) return "jamais";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "maintenant";
  const seconds = Math.floor(ms / 1000);
  if (seconds < 5) return "maintenant";
  if (seconds < 60) return "il y a " + seconds + " s";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return "il y a " + minutes + " min";
  return new Date(iso).toLocaleTimeString();
}

function FieldCard({
  label,
  stateField,
}: {
  label: string;
  stateField: StateField;
}) {
  const confidence = Math.round((stateField.confidence || 0) * 100);
  let display = "—";

  if (stateField.value !== null && stateField.value !== undefined) {
    if (Array.isArray(stateField.value)) {
      display = String(stateField.value.length);
    } else if (typeof stateField.value === "object") {
      display = "objet";
    } else if (typeof stateField.value === "boolean") {
      display = stateField.value ? "Oui" : "Non";
    } else {
      display = String(stateField.value);
    }
  }

  return (
    <article className="metric">
      <div className="metricTop">
        <span>{label}</span>
        <em>{confidence}%</em>
      </div>
      <strong>{display}</strong>
      <div className="metricMeta">
        <span>{stateField.source}</span>
        <span>{relativeTime(stateField.updated_at)}</span>
      </div>
      <div className="confidence">
        <i style={{ width: String(confidence) + "%" }} />
      </div>
    </article>
  );
}

export default function Home() {
  const [state, setState] = useState<GameState>(initialState);
  const [connected, setConnected] = useState(false);
  const [network, setNetwork] = useState<NetworkStatus | null>(null);
  const [debug, setDebug] = useState<NetworkDebug>(initialDebug);
  const [gameData, setGameData] = useState<GameDataStatus | null>(null);
  const [vision, setVision] = useState<VisionStatus | null>(null);

  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
    [],
  );
  const wsUrl = useMemo(
    () => process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws",
    [],
  );

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let retry = 0;
    let stopped = false;

    const connect = () => {
      if (stopped) return;

      socket = new WebSocket(wsUrl);
      socket.onopen = () => {
        retry = 0;
        setConnected(true);
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "game_state") {
            setState(message.payload);
          }
        } catch {
          // Ignore malformed debug frames without dropping the socket.
        }
      };
      socket.onerror = () => setConnected(false);
      socket.onclose = () => {
        setConnected(false);
        if (stopped) return;
        const delay = Math.min(1000 * 2 ** retry, 10000);
        retry += 1;
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [wsUrl]);

  useEffect(() => {
    let stopped = false;

    const refresh = async () => {
      try {
        const responses = await Promise.all([
          fetch(apiUrl + "/api/network/status", { cache: "no-store" }),
          fetch(apiUrl + "/api/network/debug", { cache: "no-store" }),
          fetch(apiUrl + "/api/game-data/status", { cache: "no-store" }),
          fetch(apiUrl + "/api/vision/status", { cache: "no-store" }),
        ]);

        if (stopped) return;

        if (responses[0].ok) setNetwork(await responses[0].json());
        if (responses[1].ok) setDebug(await responses[1].json());
        if (responses[2].ok) setGameData(await responses[2].json());
        if (responses[3].ok) setVision(await responses[3].json());
      } catch {
        if (!stopped) {
          setNetwork(null);
          setGameData(null);
          setVision(null);
        }
      }
    };

    void refresh();
    const timer = window.setInterval(refresh, 2500);

    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [apiUrl]);

  const interactives = Array.isArray(state.interactives.value)
    ? state.interactives.value
    : [];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <span className="kicker">DOFUS HYBRID OBSERVER · v0.5</span>
          <h1>Diagnostic temps réel</h1>
          <p>Réseau décodé + profil brut + données locales + vision ciblée.</p>
        </div>
        <div className={connected ? "connection online" : "connection"}>
          <span />
          {connected ? "WebSocket connecté" : "Reconnexion…"}
        </div>
      </header>

      <section className="metrics">
        <FieldCard label="Map ID" stateField={state.map_id} />
        <FieldCard label="Cellule joueur" stateField={state.player_cell} />
        <FieldCard label="Réseau" stateField={state.network_connected} />
        <FieldCard label="Interactifs" stateField={state.interactives} />
      </section>

      <section className="statusGrid">
        <article className="panel">
          <div className="panelHeader">
            <h2>Sources</h2>
            <span className="badge">lecture seule</span>
          </div>
          <div className="rows">
            <div>
              <span>Profil réseau brut</span>
              <b>{network?.profile_build ?? "non chargé"}</b>
            </div>
            <div>
              <span>Ingestion JSON décodée</span>
              <b>{network?.decoded_ingest_enabled ? "prête" : "inactive"}</b>
            </div>
            <div>
              <span>maps.sqlite</span>
              <b>{gameData?.map_interactions_ready ? "prête" : "absente"}</b>
            </div>
            <div>
              <span>Maps indexées</span>
              <b>{gameData?.map_count ?? 0}</b>
            </div>
            <div>
              <span>Fenêtre Dofus</span>
              <b>{vision?.window_found ? "détectée" : "introuvable"}</b>
            </div>
            <div>
              <span>Capture bureau complet</span>
              <b>{vision?.full_desktop_fallback ? "autorisée" : "bloquée"}</b>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Discovery réseau</h2>
            <span className="badge">{debug.messages_seen} messages</span>
          </div>
          <div className="rows compact">
            <div>
              <span>Direction</span>
              <b>{debug.last_direction}</b>
            </div>
            <div>
              <span>Wire key</span>
              <b>{debug.last_wire_key ?? "—"}</b>
            </div>
            <div>
              <span>Ambigus</span>
              <b>{debug.ambiguous_candidates}</b>
            </div>
          </div>
          <div className="candidateList">
            {debug.candidates.length === 0 ? (
              <p className="muted">Aucun candidat map/cell détecté.</p>
            ) : (
              debug.candidates.slice(0, 10).map((candidate) => (
                <div
                  className="candidate"
                  key={[
                    candidate.semantic,
                    candidate.path,
                    candidate.value,
                  ].join("-")}
                >
                  <div className="candidateText">
                    <b>{candidate.semantic}</b>
                    <code>{candidate.path}</code>
                    <small>{candidate.reason}</small>
                  </div>
                  <div className="candidateValue">
                    <strong>{candidate.value}</strong>
                    <span className={candidate.auto_apply ? "safe" : "review"}>
                      {candidate.auto_apply ? "AUTO" : "DEBUG"}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="statusGrid lower">
        <article className="panel">
          <div className="panelHeader">
            <h2>Vision ciblée</h2>
            <span className="badge">{vision?.platform ?? "—"}</span>
          </div>
          <div className="screen">
            {vision?.window_found && vision.region ? (
              <div className="windowInfo">
                <b>{vision.region.title}</b>
                <strong>
                  {vision.region.width} × {vision.region.height}
                </strong>
                <span>
                  x={vision.region.left} · y={vision.region.top}
                </span>
                <small>
                  MSS {vision.capture_dependency_ready ? "OK" : "manquant"} ·
                  OpenCV {vision.opencv_dependency_ready ? " OK" : " manquant"}
                </small>
              </div>
            ) : (
              <div className="windowInfo">
                <b>Fenêtre non détectée</b>
                <span>{vision?.window_title_query ?? "Dofus"}</span>
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Interactifs de la map</h2>
            <span className="badge">{interactives.length}</span>
          </div>
          <div className="interactiveList">
            {interactives.length === 0 ? (
              <p className="muted">
                Ils se chargeront automatiquement dès qu’un map_id sûr sera reçu.
              </p>
            ) : (
              interactives.slice(0, 40).map((item, index) => (
                <div
                  className="interactiveRow"
                  key={[
                    item.cell_id ?? "x",
                    item.interaction_id ?? "x",
                    index,
                  ].join("-")}
                >
                  <b>cell {item.cell_id ?? "—"}</b>
                  <span>gfx {item.gfx_id ?? "—"}</span>
                  <span>interaction {item.interaction_id ?? "—"}</span>
                </div>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="panel eventPanel">
        <div className="panelHeader">
          <h2>Dernier événement unifié</h2>
          <span className="badge">{state.last_event.source}</span>
        </div>
        <pre>
          {state.last_event.value
            ? JSON.stringify(state.last_event.value, null, 2)
            : "Aucun événement reçu."}
        </pre>
      </section>
    </main>
  );
}
