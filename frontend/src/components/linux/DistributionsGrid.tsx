import { useMemo, useState } from 'react';
import type { LinuxProduct, LinuxProductDetail, LinuxRelease } from '@/api/linux';
import DistributionCard from './DistributionCard';
import './DistributionsGrid.css';
import './animations.css';

interface Props {
  products: LinuxProduct[];
  details: Record<string, LinuxProductDetail>;
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
}

function pickPrimaryRelease(detail: LinuxProductDetail | undefined): LinuxRelease | null {
  if (!detail || detail.releases.length === 0) return null;
  const active = detail.releases.filter((r) => r.status === 'active');
  if (active.length === 0) return detail.releases[0];
  const lts = active.find((r) => r.lts);
  if (lts) return lts;
  return active[0];
}

export default function DistributionsGrid({
  products,
  details,
  selectedSlug,
  onSelect,
}: Props) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return products;
    return products.filter(
      (p) =>
        p.display_name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q),
    );
  }, [products, filter]);

  const totalActive = filtered.reduce((sum, p) => sum + (p.active_count ?? 0), 0);
  const totalSoon = filtered.reduce((sum, p) => sum + (p.expiring_soon_count ?? 0), 0);

  return (
    <section
      className={`linux-distros-section rounded-xl p-5 animate-linux-card-enter animate-linux-stagger-2 ${open ? 'linux-distros-section--open' : 'linux-distros-section--closed'}`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="linux-distros-section__header w-full flex flex-wrap items-center justify-between gap-3 text-left"
        aria-expanded={open}
        aria-controls="linux-distros-body"
      >
        <div className="flex items-center gap-3">
          <span
            className={`linux-distros-section__chevron material-symbols-outlined text-secondary text-[26px] ${open ? 'linux-distros-section__chevron--open' : ''}`}
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            expand_more
          </span>
          <span
            className="material-symbols-outlined text-secondary text-[22px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            grid_view
          </span>
          <h3 className="font-headline-md text-headline-md text-primary">Distribuciones</h3>
          <span className="linux-distros-section__count">
            {filtered.length}/{products.length}
          </span>
          <span className="linux-distros-section__stats hidden md:inline-flex">
            <span className="linux-distros-section__pill linux-distros-section__pill--ok">
              {totalActive} activas
            </span>
            {totalSoon > 0 && (
              <span className="linux-distros-section__pill linux-distros-section__pill--warn">
                {totalSoon} próximas EOL
              </span>
            )}
          </span>
        </div>

        <div
          className="flex items-center gap-2"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="relative">
            <span className="material-symbols-outlined absolute left-2 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">
              search
            </span>
            <input
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                if (!open) setOpen(true);
              }}
              placeholder="Filtrar distro..."
              className="linux-distros-section__filter pl-8 pr-3 py-1.5 rounded-full text-sm"
            />
          </div>
          <span
            className={`linux-distros-section__toggle-hint ${open ? '' : 'linux-distros-section__toggle-hint--blink'}`}
          >
            {open ? 'Ocultar' : 'Mostrar todas'}
          </span>
        </div>
      </button>

      <div
        id="linux-distros-body"
        className={`linux-distros-grid-wrap ${open ? 'linux-distros-grid-wrap--open' : 'linux-distros-grid-wrap--closed'}`}
        aria-hidden={!open}
      >
        <div className="linux-distros-grid grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4 mt-4">
          {filtered.map((product, idx) => (
            <DistributionCard
              key={product.slug}
              product={product}
              primaryRelease={pickPrimaryRelease(details[product.slug])}
              staggerIndex={idx % 6}
              selected={selectedSlug === product.slug}
              onSelect={() => onSelect(product.slug)}
            />
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full text-center py-8 text-on-surface-variant text-label-sm">
              No hay distribuciones que coincidan con "{filter}".
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
