import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDraftStream } from "./useDraftStream";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  private listeners = new Map<string, EventListener>();
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, listener);
  }

  fire(type: string, data: unknown) {
    const listener = this.listeners.get(type);
    if (listener) {
      const ev = new MessageEvent("message", { data: JSON.stringify(data) });
      listener(ev);
    }
  }

  close() {
    this.closed = true;
  }
}

describe("useDraftStream", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts disconnected with no events when draftId is null", () => {
    const { result } = renderHook(() => useDraftStream(null));
    expect(result.current.events).toEqual([]);
    expect(result.current.connected).toBe(false);
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("opens an EventSource for the given draftId and collects events", () => {
    const { result } = renderHook(() => useDraftStream("d1"));
    expect(FakeEventSource.instances).toHaveLength(1);
    const es = FakeEventSource.instances[0];
    expect(es.url).toBe("/v1/drafts/d1/stream");

    act(() => {
      es.fire("pick_starting", { id: "1", type: "pick_starting", ts: "t", draft_id: "d1" });
      es.fire("pick_completed", { id: "2", type: "pick_completed", ts: "t", draft_id: "d1" });
    });

    expect(result.current.events).toHaveLength(2);
    expect(result.current.events[0].type).toBe("pick_starting");
  });

  it("closes the connection on draft_completed", () => {
    const { result } = renderHook(() => useDraftStream("d1"));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.fire("draft_completed", { id: "9", type: "draft_completed", ts: "t", draft_id: "d1" });
    });

    expect(result.current.events.at(-1)?.type).toBe("draft_completed");
    expect(es.closed).toBe(true);
  });
});
