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

export default function Home() {
  const [state, setState] = useState<GameState>(initialState);
  const [connected, setConnected] = useState(false);

  const wsUrl = useMemo(
    () => process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws",
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
