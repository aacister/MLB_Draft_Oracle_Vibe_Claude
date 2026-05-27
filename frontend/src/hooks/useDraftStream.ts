// Subscribe to /v1/drafts/{id}/stream via EventSource; collect typed events.

import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { DraftEvent } from "../types";

interface UseDraftStreamResult {
  events: DraftEvent[];
  connected: boolean;
  error: string | null;
}

export function useDraftStream(draftId: string | null): UseDraftStreamResult {
  const [events, setEvents] = useState<DraftEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!draftId) return;
    setEvents([]);
    setError(null);

    const es = new EventSource(api.streamUrl(draftId));
    sourceRef.current = es;

    const handle = (ev: MessageEvent) => {
      try {
        const parsed = JSON.parse(ev.data) as DraftEvent;
        setEvents((prev) => [...prev, parsed]);
        if (parsed.type === "stream_end" || parsed.type === "draft_completed") {
          es.close();
          setConnected(false);
        }
      } catch (err) {
        setError(String(err));
      }
    };

    // Register handlers for each named event we emit on the backend.
    const eventTypes = [
      "draft_started",
      "pick_starting",
      "research_complete",
      "pick_completed",
      "team_graded",
      "draft_completed",
      "stream_end",
      "error",
    ];
    for (const type of eventTypes) {
      es.addEventListener(type, handle as EventListener);
    }

    es.onopen = () => setConnected(true);
    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, [draftId]);

  return { events, connected, error };
}
