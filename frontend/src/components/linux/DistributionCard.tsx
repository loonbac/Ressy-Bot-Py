import type { LinuxProduct, LinuxRelease } from '@/api/linux';
import { metaFor, ROLLING_SLUGS } from './distroMeta';
import './DistributionCard.css';
import './animations.css';

interface Props {
  product: LinuxProduct;
  primaryRelease: LinuxRelease | null;
  staggerIndex: number;
  selected: boolean;
  onSelect: () => void;
}

function progressFor(release: LinuxRelease | null): number {
  if (!release || !release.release_date || !release.eol_date) return 0;
  try {
    const start = Date.parse(release.release_date);
    const end = Date.parse(release.eol_date);
    const now = Date.now();
    if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return 0;
    const pct = ((now - start) / (end - start)) * 100;
    return Math.max(2, Math.min(100, Math.round(pct)));
  } catch {
    return 0;
  }
}

function statusTone(days: number | null): 'safe' | 'warning' | 'error' | 'unknown' {
  if (days === null) return 'unknown';
  if (days < 0) return 'error';
  if (days <= 90) return 'warning';
  return 'safe';
}

function formatDays(days: number | null): string {
  if (days === null) return 'Sin fecha';
  if (days < 0) return `${Math.abs(days)}d expirada`;
  if (days < 365) return `${days} días`;
  return `${days.toLocaleString('es')} días`;
}

export default function DistributionCard({
  product,
  primaryRelease,
  staggerIndex,
  selected,
  onSelect,
}: Props) {
  const meta = metaFor(product.slug);
  const isRolling = ROLLING_SLUGS.has(product.slug);
  const days = primaryRelease?.days_until_eol ?? null;
  const tone: 'safe' | 'warning' | 'error' | 'unknown' | 'rolling' = isRolling
    ? 'rolling'
    : statusTone(days);
  const progress = isRolling ? 100 : progressFor(primaryRelease);
  const cycleLabel = primaryRelease ? `${primaryRelease.cycle}` : '—';
  const labelText = isRolling
    ? 'Rolling release'
    : primaryRelease?.lts
      ? `LTS ${cycleLabel}`
      : `Activa ${cycleLabel}`;
  const staggerClass = `animate-linux-stagger-${Math.min(staggerIndex + 1, 6)}`;

  const toneIcon =
    tone === 'error'
      ? 'warning'
      : tone === 'warning'
        ? 'priority_high'
        : tone === 'safe'
          ? 'check_circle'
          : tone === 'rolling'
            ? 'all_inclusive'
            : 'help';

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`linux-distro-card linux-distro-card--${tone} rounded-xl p-5 text-left flex flex-col gap-3 animate-linux-card-enter ${staggerClass} ${selected ? 'linux-distro-card--selected' : ''}`}
      style={{ ['--distro-color' as string]: meta.color }}
      aria-pressed={selected}
    >
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-3">
          <div
            className="linux-distro-card__icon w-11 h-11 rounded-lg flex items-center justify-center"
            style={{ background: `${meta.color}1A`, color: meta.color }}
          >
            <span className="material-symbols-outlined text-[26px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              {meta.icon}
            </span>
          </div>
          <div>
            <h3 className="font-headline-md text-headline-md text-on-surface leading-tight">
              {product.display_name}
            </h3>
            <span
              className="text-label-sm px-2 py-0.5 rounded font-bold inline-block mt-1"
              style={{ background: `${meta.color}1A`, color: meta.color }}
            >
              {labelText}
            </span>
          </div>
        </div>
        {product.stale && (
          <span
            className="material-symbols-outlined text-secondary text-[18px] animate-linux-warning-pulse"
            title="Datos desactualizados"
          >
            schedule
          </span>
        )}
      </div>

      <div className="flex justify-between text-label-sm text-on-surface-variant">
        <span>{isRolling ? 'Modelo' : primaryRelease?.lts ? 'LTS' : 'Lanzamiento'}</span>
        <span className="font-bold">
          {isRolling
            ? 'Sin EOL'
            : primaryRelease?.eol_date
              ? `EOL: ${primaryRelease.eol_date}`
              : 'EOL: —'}
        </span>
      </div>

      <div className="linux-distro-card__bar h-2 rounded-full overflow-hidden">
        <div
          className={`linux-distro-card__bar-fill h-full rounded-full animate-linux-bar-fill ${isRolling ? 'linux-distro-card__bar-fill--rolling' : ''}`}
          style={{
            ['--bar-target' as string]: `${progress}%`,
            width: `${progress}%`,
            background: meta.color,
          }}
        />
      </div>

      <div className="flex justify-between items-center">
        <div className={`flex items-center gap-1 linux-distro-card__days linux-distro-card__days--${tone}`}>
          <span
            className="material-symbols-outlined text-[18px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {toneIcon}
          </span>
          <span className="font-bold">{isRolling ? 'Sin caducidad' : formatDays(days)}</span>
        </div>
        <span className="linux-distro-card__cta text-secondary text-label-sm font-bold flex items-center gap-1">
          <span>Ver más</span>
          <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
        </span>
      </div>

      <span className="linux-distro-card__count text-[10px] uppercase tracking-widest text-on-surface-variant">
        {isRolling
          ? 'Actualización continua · sin ventanas de release'
          : `${product.release_count} versiones · ${product.active_count} activas${product.expiring_soon_count > 0 ? ` · ${product.expiring_soon_count} próximas EOL` : ''}`}
      </span>
    </button>
  );
}
