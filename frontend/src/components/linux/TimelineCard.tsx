import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { LinuxProduct, LinuxProductDetail, LinuxRelease } from '@/api/linux';
import { metaFor, ROLLING_SLUGS } from './distroMeta';
import './TimelineCard.css';
import './animations.css';

interface Props {
  products: LinuxProduct[];
  details: Record<string, LinuxProductDetail>;
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
}

type Status = 'upcoming' | 'active' | 'past';

const ROTATE_MS = 6000;
const ROW_HEIGHT = 56; // px aprox por release (icon dot + 2 lines + gap)
const MIN_VISIBLE = 3;
const MAX_VISIBLE_CAP = 30;

function statusFor(release: LinuxRelease): Status {
  if (release.release_date) {
    const t = Date.parse(release.release_date);
    if (!Number.isNaN(t) && t > Date.now()) return 'upcoming';
  }
  if (release.status === 'active') return 'active';
  return 'past';
}

const STATUS_ICON: Record<Status, string> = {
  upcoming: 'upcoming',
  active: 'stars',
  past: 'history',
};

const STATUS_LABEL: Record<Status, string> = {
  upcoming: 'Próxima',
  active: 'Activa',
  past: 'Pasada',
};

export default function TimelineCard({
  products,
  details,
  selectedSlug,
  onSelect,
}: Props) {
  const [paused, setPaused] = useState(false);
  const [visibleCount, setVisibleCount] = useState(6);
  const timerRef = useRef<number | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const headerRef = useRef<HTMLDivElement | null>(null);

  const slugs = useMemo(() => products.map((p) => p.slug), [products]);
  const totalSlugs = slugs.length;
  const currentIdx = selectedSlug ? slugs.indexOf(selectedSlug) : 0;
  const effectiveIdx = currentIdx >= 0 ? currentIdx : 0;
  const currentSlug = slugs[effectiveIdx] ?? null;
  const detail = currentSlug ? (details[currentSlug] ?? null) : null;

  // Auto-rotate through distros.
  useEffect(() => {
    if (paused || totalSlugs <= 1) return;
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      const nextIdx = (effectiveIdx + 1) % totalSlugs;
      onSelect(slugs[nextIdx]);
    }, ROTATE_MS);
    return () => {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [paused, totalSlugs, effectiveIdx, slugs, onSelect]);

  const sorted = useMemo<LinuxRelease[]>(() => {
    if (!detail) return [];
    return [...detail.releases].sort((a, b) => {
      const ad = a.release_date ? Date.parse(a.release_date) : 0;
      const bd = b.release_date ? Date.parse(b.release_date) : 0;
      return bd - ad;
    });
  }, [detail]);

  // Compute how many releases fit in the available body area.
  useLayoutEffect(() => {
    const body = bodyRef.current;
    if (!body) return;

    const recompute = () => {
      const bodyHeight = body.clientHeight;
      const available = Math.max(0, bodyHeight - 8); // tiny breathing room
      const fit = Math.floor(available / ROW_HEIGHT);
      // Add 2 extra rows so they overflow and get masked = "layer behind" effect.
      const next = Math.min(MAX_VISIBLE_CAP, Math.max(MIN_VISIBLE, fit + 2));
      setVisibleCount((prev) => (prev === next ? prev : next));
    };

    recompute();
    const ro = new ResizeObserver(recompute);
    ro.observe(body);
    if (headerRef.current) ro.observe(headerRef.current);
    return () => ro.disconnect();
  }, [detail?.slug]);

  if (slugs.length === 0) {
    return (
      <div className="linux-timeline-card linux-timeline-card--empty rounded-xl p-6 flex flex-col items-center justify-center text-center">
        <span className="material-symbols-outlined text-4xl text-outline-variant mb-3">
          timeline
        </span>
        <p className="text-on-surface-variant text-label-sm">
          Sin distribuciones cargadas todavía.
        </p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="linux-timeline-card linux-timeline-card--empty rounded-xl p-6 flex flex-col items-center justify-center text-center">
        <span
          className="material-symbols-outlined text-3xl text-secondary mb-2 animate-linux-sync-spin"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          progress_activity
        </span>
        <p className="text-on-surface-variant text-label-sm">
          Cargando timeline de {currentSlug}...
        </p>
      </div>
    );
  }

  const meta = metaFor(detail.slug);
  const isRolling = ROLLING_SLUGS.has(detail.slug);
  const visible = sorted.slice(0, visibleCount);
  const overflowCount = Math.max(0, sorted.length - visibleCount);

  const handlePrev = () => {
    const prev = (effectiveIdx - 1 + totalSlugs) % totalSlugs;
    onSelect(slugs[prev]);
  };
  const handleNext = () => {
    const next = (effectiveIdx + 1) % totalSlugs;
    onSelect(slugs[next]);
  };

  return (
    <div
      className="linux-timeline-card rounded-xl flex flex-col relative overflow-hidden w-full flex-1 animate-linux-card-enter animate-linux-stagger-3"
      style={{ ['--distro-color' as string]: meta.color }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="linux-timeline-card__inner p-5 flex-1 min-h-0 flex flex-col">
        <div className="linux-timeline-card__watermark">
          <span className="material-symbols-outlined" style={{ fontSize: '100px' }}>
            {meta.icon}
          </span>
        </div>

        <div
          ref={headerRef}
          className="flex items-center justify-between gap-3 mb-4 flex-wrap relative z-10"
        >
          <h3
            key={detail.slug}
            className="font-headline-md text-headline-md text-primary flex items-center gap-2 animate-linux-row-fade-in"
          >
            <span
              className="material-symbols-outlined text-[22px]"
              style={{ color: meta.color, fontVariationSettings: "'FILL' 1" }}
            >
              {meta.icon}
            </span>
            <span>Timeline: {detail.display_name}</span>
          </h3>

          {totalSlugs > 1 && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handlePrev}
                className="linux-timeline-card__nav-btn"
                aria-label="Distribución anterior"
              >
                <span className="material-symbols-outlined text-[18px]">chevron_left</span>
              </button>
              <span className="linux-timeline-card__counter">
                {effectiveIdx + 1}/{totalSlugs}
              </span>
              <button
                type="button"
                onClick={handleNext}
                className="linux-timeline-card__nav-btn"
                aria-label="Distribución siguiente"
              >
                <span className="material-symbols-outlined text-[18px]">chevron_right</span>
              </button>
              <span
                className={`linux-timeline-card__play-state ${paused ? 'linux-timeline-card__play-state--paused' : ''}`}
                aria-hidden
                title={paused ? 'Pausado (hover sobre la card)' : 'Auto-rotación activa'}
              >
                <span
                  className="material-symbols-outlined text-[16px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  {paused ? 'pause_circle' : 'play_circle'}
                </span>
              </span>
            </div>
          )}
        </div>

        <div ref={bodyRef} className="linux-timeline-card__body relative flex-1 min-h-0">
          {isRolling ? (
            <div
              key={`rolling-${detail.slug}`}
              className="linux-timeline-card__rolling-hero"
              style={{ ['--distro-color' as string]: meta.color }}
            >
              <div className="linux-timeline-card__rolling-glow" />
              <div className="linux-timeline-card__rolling-icon">
                <span
                  className="material-symbols-outlined"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  all_inclusive
                </span>
              </div>
              <h4 className="linux-timeline-card__rolling-title font-display">
                Sin caducidad
              </h4>
              <p className="linux-timeline-card__rolling-subtitle">
                {detail.display_name} es una distribución <b>rolling release</b>.
              </p>
              <p className="linux-timeline-card__rolling-tagline">
                Actualizaciones continuas — sin versiones que expiren ni saltos
                mayores. Mantente al día con un simple{' '}
                <code className="linux-timeline-card__rolling-code">
                  {detail.slug === 'arch'
                    ? 'pacman -Syu'
                    : detail.slug === 'manjaro' || detail.slug === 'endeavouros'
                      ? 'pacman -Syu'
                      : detail.slug === 'bazzite'
                        ? 'rpm-ostree upgrade'
                        : 'pacman -Syu'}
                </code>
                .
              </p>
              <div className="linux-timeline-card__rolling-chips">
                <span className="linux-timeline-card__rolling-chip">
                  <span className="material-symbols-outlined text-[14px]">bolt</span>
                  Continuo
                </span>
                <span className="linux-timeline-card__rolling-chip">
                  <span className="material-symbols-outlined text-[14px]">verified</span>
                  Siempre soportado
                </span>
                <span className="linux-timeline-card__rolling-chip">
                  <span className="material-symbols-outlined text-[14px]">refresh</span>
                  Sin EOL
                </span>
              </div>
            </div>
          ) : (
            <>
              <div className="linux-timeline-card__line animate-linux-timeline-grow" />

              {visible.length === 0 && (
                <div className="linux-timeline-card__empty-hero">
                  <span
                    className="material-symbols-outlined linux-timeline-card__empty-icon"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    cloud_sync
                  </span>
                  <h4 className="linux-timeline-card__empty-title font-display">
                    Sin datos aún
                  </h4>
                  <p className="linux-timeline-card__empty-subtitle">
                    Aún no se han sincronizado releases de {detail.display_name}.
                    Espera el próximo tick del scheduler o usa "Refrescar ahora".
                  </p>
                </div>
              )}

              <div
                key={detail.slug}
                className="linux-timeline-card__batch flex flex-col gap-3"
              >
            {visible.map((release, idx) => {
              const status = isRolling ? 'active' : statusFor(release);
              return (
                <div
                  key={`${detail.slug}-${release.cycle}-${idx}`}
                  className="flex gap-4 relative linux-timeline-card__row"
                  style={{ animationDelay: `${0.06 * idx}s` }}
                >
                  <div
                    className={`linux-timeline-card__dot linux-timeline-card__dot--${status} animate-linux-timeline-dot-pop z-10 w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0`}
                    style={{ animationDelay: `${0.06 * idx}s` }}
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      {isRolling ? 'all_inclusive' : STATUS_ICON[status]}
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="font-bold text-sm text-on-surface leading-tight">
                        {detail.display_name}{' '}
                        {isRolling ? (
                          <span className="font-normal text-on-surface-variant">
                            (rolling)
                          </span>
                        ) : (
                          <>
                            {release.cycle}
                            {release.codename && (
                              <span className="font-normal text-on-surface-variant ml-1">
                                ({release.codename})
                              </span>
                            )}
                          </>
                        )}
                      </h4>
                      <span
                        className={`linux-timeline-card__chip linux-timeline-card__chip--${status}`}
                      >
                        {isRolling
                          ? 'Rolling'
                          : release.lts
                            ? `${STATUS_LABEL[status]} · LTS`
                            : STATUS_LABEL[status]}
                      </span>
                    </div>
                    <p className="text-[11px] text-on-surface-variant mt-0.5">
                      {isRolling ? (
                        'Modelo de actualización continua.'
                      ) : (
                        <>
                          {release.release_date ? release.release_date : '?'}
                          {' → '}
                          {release.eol_date ?? 'sin fecha'}
                          {release.latest_version && ` · v${release.latest_version}`}
                        </>
                      )}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

              {overflowCount > 0 && (
                <p className="linux-timeline-card__overflow-hint text-[10px] uppercase tracking-widest text-on-surface-variant mt-3 text-right">
                  +{overflowCount} versiones anteriores
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {totalSlugs > 1 && (
        <div className="linux-timeline-card__footer">
          <div className="linux-timeline-card__dots flex gap-1 px-5 pb-2 pt-1 flex-wrap">
            {slugs.map((slug, i) => {
              const slugMeta = metaFor(slug);
              return (
                <button
                  key={slug}
                  type="button"
                  onClick={() => onSelect(slug)}
                  className={`linux-timeline-card__dot-nav ${i === effectiveIdx ? 'linux-timeline-card__dot-nav--active' : ''}`}
                  style={
                    i === effectiveIdx
                      ? { background: slugMeta.color }
                      : undefined
                  }
                  aria-label={`Ver ${slug}`}
                  title={slug}
                />
              );
            })}
          </div>
          <div className="linux-timeline-card__progress">
            <div
              key={`${detail.slug}-${paused}`}
              className={`linux-timeline-card__progress-fill ${paused ? 'linux-timeline-card__progress-fill--paused' : ''}`}
              style={{
                animationDuration: `${ROTATE_MS}ms`,
                background: meta.color,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
