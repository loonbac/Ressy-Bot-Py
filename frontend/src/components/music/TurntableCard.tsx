import { useEffect, useRef, useState } from 'react';
import type { MusicNowPlaying } from '@/api/music';
import './TurntableCard.css';

interface Props {
  nowPlaying: MusicNowPlaying | null;
  guildName?: string;
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

const PETALS = [
  { left: '8%',  top: '12%', delay: '0s',   duration: '7s'  },
  { left: '38%', top: '6%',  delay: '2s',   duration: '8s'  },
  { left: '70%', top: '14%', delay: '4s',   duration: '6s'  },
  { left: '88%', top: '40%', delay: '1s',   duration: '9s'  },
  { left: '20%', top: '60%', delay: '3.5s', duration: '7s'  },
];

const BAR_COUNT = 12;
const PROGRESS_TICK_MS = 500;

export default function TurntableCard({ nowPlaying, guildName }: Props) {
  const track = nowPlaying?.current_track ?? null;
  const isPlaying = Boolean(nowPlaying?.is_playing);
  const isPaused = Boolean(nowPlaying?.is_paused);
  const spinning = isPlaying && !isPaused;

  // Local elapsed counter — backend doesn't expose elapsed, fake forward motion while playing
  const [elapsed, setElapsed] = useState(0);
  const lastTrackKeyRef = useRef<string>('');

  useEffect(() => {
    const key = track ? `${track.url}::${track.title}` : '';
    if (key !== lastTrackKeyRef.current) {
      lastTrackKeyRef.current = key;
      setElapsed(0);
    }
  }, [track]);

  useEffect(() => {
    if (!spinning || !track) return;
    const id = window.setInterval(() => {
      setElapsed((prev) => {
        const dur = track.duration_seconds || 0;
        const next = prev + PROGRESS_TICK_MS / 1000;
        if (dur > 0 && next > dur) return 0;
        return next;
      });
    }, PROGRESS_TICK_MS);
    return () => window.clearInterval(id);
  }, [spinning, track]);

  const totalSeconds = track?.duration_seconds ?? 0;
  const progressPct =
    totalSeconds > 0 ? Math.min(100, (elapsed / totalSeconds) * 100) : 0;

  let stateName: 'idle' | 'playing' | 'paused' = 'idle';
  let pillClass = 'music-turntable-card__pill--idle';
  let pillLabel = 'Sin reproducción';
  if (track && spinning) {
    stateName = 'playing';
    pillClass = '';
    pillLabel = 'Reproduciendo en vivo';
  } else if (track && isPaused) {
    stateName = 'paused';
    pillClass = 'music-turntable-card__pill--paused';
    pillLabel = 'En pausa';
  }

  const albumKey = track ? `${track.thumbnail_url}-${track.title}` : 'empty';

  return (
    <div
      className={`music-turntable-card music-turntable-card--${stateName} animate-turntable-card-reveal rounded-2xl p-5 h-full flex flex-col min-h-0 overflow-hidden shadow-[0px_18px_38px_rgba(168,0,33,0.08)]`}
    >
      <div className="music-turntable-card__pattern" />

      {PETALS.map((p, i) => (
        <span
          key={i}
          className="music-turntable-card__petal animate-turntable-petal"
          style={{
            left: p.left,
            top: p.top,
            animationDelay: p.delay,
            animationDuration: p.duration,
          }}
          aria-hidden
        />
      ))}

      <div className="relative z-10 flex flex-col h-full min-h-0">
        <div className="flex items-center justify-between mb-3 flex-shrink-0">
          <div className="flex items-center gap-2">
            <span
              className="material-symbols-outlined text-secondary text-[22px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              album
            </span>
            <span className="font-headline-md text-headline-md text-primary leading-none">
              En el Tocadiscos
            </span>
          </div>
          <span
            className={`music-turntable-card__pill ${pillClass}`}
            aria-live="polite"
          >
            <span className="music-turntable-card__pill-dot" />
            {pillLabel}
          </span>
        </div>

        <div className="flex-1 min-h-0 flex items-center gap-6">
          <div className="music-turntable">
            <span className="music-turntable__edge-glow" aria-hidden />
            <div className="music-turntable__platter">
              <div
                className={`music-turntable__rotor ${
                  spinning ? 'animate-turntable-spin' : ''
                }`}
              >
                <div className="music-turntable__grooves" />
                <div className="music-turntable__shine" />
                <div
                  key={albumKey}
                  className={
                    'music-turntable__label animate-turntable-album-reveal ' +
                    (track?.thumbnail_url ? '' : 'music-turntable__label--placeholder')
                  }
                >
                  {track?.thumbnail_url ? (
                    <img
                      src={track.thumbnail_url}
                      alt={track.title || 'Portada'}
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  ) : (
                    <span
                      className="material-symbols-outlined text-white"
                      style={{ fontSize: 36, fontVariationSettings: "'FILL' 1" }}
                    >
                      music_note
                    </span>
                  )}
                </div>
              </div>
              <span className="music-turntable__spindle" aria-hidden />
            </div>
            <div className="music-turntable__tonearm" aria-hidden>
              <div className="music-turntable__tonearm-inner">
                <div className="music-turntable__tonearm-shaft" />
                <div className="music-turntable__tonearm-base" />
                <div className="music-turntable__tonearm-head">
                  <div className="music-turntable__tonearm-needle" />
                </div>
              </div>
            </div>
          </div>

          {track ? (
            <div className="music-turntable-card__info">
              <p className="text-[11px] uppercase tracking-widest text-tertiary">
                {guildName ? `Reproduciendo en · ${guildName}` : 'Pista actual'}
              </p>
              <h3
                className="music-turntable-card__title line-clamp-2"
                title={track.title}
              >
                {track.title || 'Sin título'}
              </h3>
              <div className="music-turntable-card__meta-row">
                <span>
                  <span className="material-symbols-outlined text-[16px]">person</span>
                  {track.requester_name || 'Anónimo'}
                </span>
                <span>
                  <span className="material-symbols-outlined text-[16px]">schedule</span>
                  {formatDuration(elapsed)} / {formatDuration(track.duration_seconds)}
                </span>
              </div>
              <div className="music-turntable-card__progress">
                <div
                  className="music-turntable-card__progress-fill"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <div className="music-turntable-card__waveform" aria-hidden>
                {Array.from({ length: BAR_COUNT }).map((_, i) => (
                  <span key={i} className="music-turntable-card__bar" />
                ))}
              </div>
            </div>
          ) : (
            <div className="music-turntable-card__empty">
              <p className="text-[11px] uppercase tracking-widest text-tertiary">
                Tocadiscos en silencio
              </p>
              <h3 className="font-headline-md text-headline-md text-on-surface leading-tight">
                Esperando una nueva pista...
              </h3>
              <p className="text-sm text-tertiary max-w-md">
                Cuando alguien use{' '}
                <span className="font-mono text-primary">/play</span> en Discord, la
                portada del video aparecerá aquí girando suavemente.
              </p>
              <div className="music-turntable-card__waveform mt-1" aria-hidden>
                {Array.from({ length: BAR_COUNT }).map((_, i) => (
                  <span
                    key={i}
                    className="music-turntable-card__bar"
                    style={{ opacity: 0.25 }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
