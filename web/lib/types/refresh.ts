// T42 / S11a: GET /api/refresh/status, mirroring `refresh_worker.status()`
// key for key (api/tests/routers/test_refresh_router.py parses this
// interface). Timestamps are ISO-8601 with a trailing `Z`.
export interface RefreshStatus {
  running: boolean;
  disabled_reason: string | null;
  interval_seconds: number;
  last_tick_started: string | null;
  last_tick_finished: string | null;
  last_tick_ok: number;
  last_tick_failed: number;
  next_tick_at: string | null;
  queue_depth: number;
  backoff_seconds: number;
  server_time: string | null;
}
