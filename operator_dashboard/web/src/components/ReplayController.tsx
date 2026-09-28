import { useMemo } from "react";

type Props = {
  isPlaying: boolean;
  speed: number;
  currentTimeMs: number;
  durationMs: number;
  clockStart: string;
  onTogglePlay: () => void;
  onSetSpeed: (s: number) => void;
  onSeek: (ms: number) => void;
  onStep: (deltaSec: number) => void;
};

const SPEEDS = [0.5, 1, 2, 5, 10, 30, 60, 120];

export default function ReplayController({
  isPlaying,
  speed,
  currentTimeMs,
  durationMs,
  clockStart,
  onTogglePlay,
  onSetSpeed,
  onSeek,
  onStep,
}: Props) {
  // Format local clock time and elapsed string
  const { clockStr, elapsedStr } = useMemo(() => {
    let baseDate: Date;
    try {
      baseDate = new Date(clockStart);
      if (isNaN(baseDate.getTime())) baseDate = new Date("2026-09-17T07:00:00+08:00");
    } catch {
      baseDate = new Date("2026-09-17T07:00:00+08:00");
    }

    const safeMs = Math.max(0, currentTimeMs || 0);
    const currentDt = new Date(baseDate.getTime() + safeMs);
    const clockStr = currentDt.toLocaleTimeString("en-US", {
      timeZone: "Asia/Kuala_Lumpur",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });

    const totalSec = Math.floor(safeMs / 1000);
    const hrs = Math.floor(totalSec / 3600);
    const mins = Math.floor((totalSec % 3600) / 60);
    const secs = totalSec % 60;
    const elapsedStr =
      hrs > 0
        ? `+${hrs}h ${mins.toString().padStart(2, "0")}m ${secs.toString().padStart(2, "0")}s`
        : `+${mins}m ${secs.toString().padStart(2, "0")}s`;

    return { clockStr, elapsedStr };
  }, [clockStart, currentTimeMs]);

  const maxMs = Math.max(1000, durationMs);

  return (
    <div className="replay-controller">
      {/* Prominent Digital Clock Header */}
      <div className="replay-clock-card" aria-live="polite">
        <div className="replay-clock-digits">
          <span className="replay-time-main">{clockStr}</span>
          <span className="replay-time-elapsed">{elapsedStr}</span>
        </div>
        <div className="replay-clock-badge">
          <span className={`replay-status-dot ${isPlaying ? "live" : "paused"}`} />
          {isPlaying ? `REPLAY (${speed}x)` : "PAUSED"}
        </div>
      </div>

      {/* Scrubber Bar */}
      <div className="replay-scrubber-wrap">
        <span className="replay-scrubber-bound">00:00</span>
        <input
          type="range"
          className="replay-scrubber-slider"
          min={0}
          max={maxMs}
          step={1000}
          value={Math.min(maxMs, Math.max(0, currentTimeMs || 0))}
          onChange={(e) => onSeek(Number(e.target.value))}
          aria-label="Replay Time Scrubber"
        />
        <span className="replay-scrubber-bound">
          {Math.floor(maxMs / 60000)}m
        </span>
      </div>

      {/* Playback Controls Toolbar */}
      <div className="replay-toolbar">
        <div className="replay-main-btns">
          <button
            type="button"
            className="replay-btn step-btn"
            onClick={() => onStep(-30)}
            title="Step backward 30s"
            aria-label="Step backward 30 seconds"
          >
            -30s
          </button>

          <button
            type="button"
            className={`replay-btn play-btn ${isPlaying ? "playing" : ""}`}
            onClick={onTogglePlay}
            title={isPlaying ? "Pause replay" : "Start replay"}
            aria-label={isPlaying ? "Pause simulation replay" : "Start simulation replay"}
          >
            {isPlaying ? "⏸ Pause" : "▶ Play"}
          </button>

          <button
            type="button"
            className="replay-btn step-btn"
            onClick={() => onStep(30)}
            title="Step forward 30s"
            aria-label="Step forward 30 seconds"
          >
            +30s
          </button>

          <button
            type="button"
            className="replay-btn reset-btn"
            onClick={() => onSeek(0)}
            title="Restart from 00:00"
            aria-label="Reset simulation replay to beginning"
          >
            ⏮ Reset
          </button>
        </div>

        {/* Speed Selector Buttons */}
        <div className="replay-speed-group">
          <span className="replay-speed-label">Speed:</span>
          <div className="replay-speed-pills">
            {SPEEDS.map((s) => (
              <button
                key={s}
                type="button"
                className={`replay-speed-btn ${speed === s ? "active" : ""}`}
                onClick={() => onSetSpeed(s)}
                aria-label={`Set playback speed to ${s}x`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
