"use client";

import { useEffect, useMemo, useState } from "react";

type StateField = {
  value: unknown;
  source: string;
  confidence: number;
  updated_at: string;
};

type GameState = {
  map_id: StateField;
  player_cell: StateField;
  in_fight: StateField;
  my_turn: StateField;
  popup_visible: StateField;
  interactives: StateField;
  last_event: StateField;
};

type NetworkStatus = {
  enabled: boolean;
  profile_build: string;
  layouts: Record<string, unknown>;
};

type GameDataStatus = {
  path: string;
  exists: boolean;
  map_interactions_ready: boolean;
  map_interactions_columns: string[];
};

const emptyField: StateField = {
  value: null,
  source: "system",
  confidence: 0,
  updated_at: "",
};

const initialState: GameState = {
  map_id: emptyField,
  player_cell: emptyField,
  in_fight: emptyField,
  my_turn: emptyField,
  popup_visible: emptyField,
  interactives: emptyField,
  last_event: emptyField,
};

function FieldCard({
  label,
  field,
}: {
  label: string;
  field: StateField;
}) {
  const confidence = Math.round((field.confidence ?? 0) * 100);

  return (
    <article className="card">
      <span className="eyebrow">{label}</span>
      <strong className="value">
        {field.value === null || field.value === undefined
          ? "—"
          : typeof field.value === "object"
            ? JSON.stringify(field.value)
            : String(field.value)}
      </strong>
      <div className="meta">
        <span>{field.source}</span>
        <span>{confidence}%</span>
      </div>
      <div className="confidence">
        <div style={{ width: `${confidence}%` }} />
      </div>
    </article>
  );
}

function InfoCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="card">
      <span className="eyebrow">{label}</span>
      <strong className="value">{value}</strong>
      <div className="meta">
        <span>{detail}</span>
      </div>
    </article>
  );
}

export default function Home() {
  const [state, setState] = useState<GameState>(initialState);
  const [connected, setConnected] = useState(false);
  const [network, setNetwork] = useState<NetworkStatus | null>(null);
  const [gameData, setGameData] = useState<GameDataStatus | null>(null);

  const wsUrl = useMemo(
    () => process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws",
    [],
  );
  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
    [],
  );

  useEffect(() => {
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "game_state") {
        setState(message.payload);
      }
    };

    return () => ws.close();
  }, [wsUrl]);

  useEffect(() => {
    let cancelled = false;

    const refreshStatus = async () => {
      try {
        const [networkResponse, dataResponse] = await Promise.all([
          fetch(`${apiUrl}/api/network/status`, { cache: "no-store" }),
          fetch(`${apiUrl}/api/game-data/status`, { cache: "no-store" }),
        ]);

        if (!cancelled && networkResponse.ok) {
          setNetwork(await networkResponse.json());
        }
        if (!cancelled && dataResponse.ok) {
          setGameData(await dataResponse.json());
        }
      } catch {
        if (!cancelled) {
          setNetwork(null);
          setGameData(null);
        }
      }
    };

    void refreshStatus();
    const interval = window.setInterval(refreshStatus, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [apiUrl]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <span className="kicker">DOFUS HYBRID OBSERVER</span>
          <h1>Dashboard temps réel</h1>
        </div>
        <div className={connected ? "status online" : "status"}>
          <span />
          {connected ? "Backend connecté" : "Backend hors ligne"}
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">ÉTAT UNIFIÉ</p>
          <h2>Réseau + données locales + vision</h2>
          <p>
            Chaque valeur affiche sa source et son niveau de confiance. Le
            contrôleur graphique reste désactivé par défaut.
          </p>
        </div>
      </section>

      <section className="grid">
        <InfoCard
          label="Profil réseau"
          value={network?.profile_build ?? "Non chargé"}
          detail={network?.enabled ? "observer activé" : "observer passif / replay"}
        />
        <InfoCard
          label="Maps SQLite"
          value={gameData?.map_interactions_ready ? "Prêt" : "Non chargé"}
          detail={gameData?.path ?? "aucune base"}
        />
        <InfoCard
          label="WebSocket"
          value={connected ? "Connecté" : "Hors ligne"}
          detail="état temps réel"
        />
      </section>

      <section className="grid" style={{ marginTop: 14 }}>
        <FieldCard label="Map ID" field={state.map_id} />
        <FieldCard label="Player cell" field={state.player_cell} />
        <FieldCard label="Combat" field={state.in_fight} />
        <FieldCard label="Mon tour" field={state.my_turn} />
        <FieldCard label="Popup" field={state.popup_visible} />
        <FieldCard label="Interactifs" field={state.interactives} />
      </section>

      <section className="panel">
        <span className="eyebrow">DERNIER ÉVÉNEMENT</span>
        <pre>
          {state.last_event.value
            ? JSON.stringify(state.last_event.value, null, 2)
            : "Aucun événement reçu pour le moment."}
        </pre>
      </section>
    </main>
  );
}
