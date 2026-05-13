import './AnimatedScrapeButton.css';

export type ScrapeState = 'idle' | 'scraping' | 'success' | 'error';

const CONFIG: Record<
  ScrapeState,
  { icon: string; label: string; fill: boolean; iconAnim: string; btnAnim: string }
> = {
  idle:     { icon: 'precision_manufacturing', label: 'Ejecutar Scraper', fill: true,  iconAnim: '',                btnAnim: '' },
  scraping: { icon: 'progress_activity',       label: 'Scrapeando...',    fill: false, iconAnim: 'animate-spin',    btnAnim: 'animate-bb-scrape-pulse' },
  success:  { icon: 'check_circle',            label: '¡Listo!',          fill: true,  iconAnim: 'animate-spin-in', btnAnim: 'animate-btn-success' },
  error:    { icon: 'error',                   label: 'Error',            fill: true,  iconAnim: 'animate-spin-in', btnAnim: 'animate-shake' },
};

export default function AnimatedScrapeButton({
  state,
  onClick,
}: {
  state: ScrapeState;
  onClick: () => void;
}) {
  const { icon, label, fill, iconAnim, btnAnim } = CONFIG[state];
  return (
    <button
      onClick={onClick}
      disabled={state === 'scraping'}
      className={`bb-scrape-btn px-4 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed bloom-btn ${btnAnim}`}
    >
      <span
        key={state}
        className={`material-symbols-outlined text-[18px] ${iconAnim}`}
        style={fill ? { fontVariationSettings: "'FILL' 1" } : undefined}
      >
        {icon}
      </span>
      {label}
    </button>
  );
}
