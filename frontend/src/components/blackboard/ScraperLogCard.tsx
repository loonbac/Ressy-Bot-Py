import { useEffect, useRef } from 'react';
import type { ScrapeStep } from '@/api/blackboard';
import './ScraperLogCard.css';
import './animations.css';

interface Props {
  steps: ScrapeStep[];
  running: boolean;
  onRefresh: () => void;
}

export default function ScraperLogCard({ steps, running, onRefresh }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps]);

  return (
    <div className="bb-log-card rounded-2xl p-4 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className={`material-symbols-outlined text-secondary text-[20px] ${
              running ? 'animate-pulse' : ''
            }`}
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            terminal
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none">
            Scraper Log
          </span>
          {running && (
            <span className="text-[10px] uppercase tracking-wider font-bold text-secondary bg-secondary/10 px-2 py-0.5 rounded-full animate-bb-status-pulse">
              RUNNING
            </span>
          )}
          <span className="text-label-sm text-tertiary px-2 py-0.5 rounded-full bg-surface-container-highest ml-1">
            {steps.length}
          </span>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="text-label-sm text-tertiary hover:text-secondary transition-colors flex items-center gap-1"
          title="Refrescar logs"
        >
          <span className="material-symbols-outlined text-[18px]">refresh</span>
        </button>
      </div>

      <div
        ref={scrollRef}
        className="bb-log-card__terminal flex-1 min-h-0 overflow-y-auto rounded-lg p-2"
      >
        {steps.length === 0 ? (
          <div className="text-[11px] text-zinc-500 italic p-2">
            Sin logs todavía. Ejecuta el scraper para ver el progreso paso a paso.
          </div>
        ) : (
          steps.map((s, i) => (
            <div
              key={`${s.ts}-${i}`}
              className="bb-log-card__line animate-bb-row-enter"
              style={{ animationDelay: `${Math.min(i * 0.02, 0.3)}s` }}
            >
              <span className="bb-log-card__elapsed">{s.elapsed_s.toFixed(2)}s</span>
              <span className={`bb-log-card__level-${s.level}`}>{s.level}</span>
              <span className="bb-log-card__msg">{s.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
