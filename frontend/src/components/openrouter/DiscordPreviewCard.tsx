import { useMemo, useState } from 'react';
import './DiscordPreviewCard.css';
import type { OpenRouterModel, PhaseSummary, RankingResponse } from '@/api/openrouter';

type Variant = 'precios' | 'ranking' | 'weekly';

const VARIANT_META: Record<Variant, { label: string; icon: string; color: string; title: string }> = {
  precios: {
    label: 'Precios',
    icon: 'payments',
    color: '#b71329',
    title: '💰 Precios OpenRouter',
  },
  ranking: {
    label: 'Ranking',
    icon: 'leaderboard',
    color: '#5865f2',
    title: '🏆 Top Modelos por Fase SDD',
  },
  weekly: {
    label: 'Reporte Semanal',
    icon: 'event',
    color: '#3ba55c',
    title: '📊 Reporte Semanal de Precios',
  },
};

interface Props {
  models: OpenRouterModel[];
  maxCount?: number;
  botName?: string;
  botAvatarUrl?: string;
  phases?: PhaseSummary[];
  rankings?: Record<string, RankingResponse | null>;
}

function formatPrice(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value < 0) return 'var.';
  if (value === 0) return 'gratis';
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`;
}

function getRankClass(rank: number): string {
  if (rank === 1) return 'or-discord-preview-card__rank or-discord-preview-card__rank--gold';
  if (rank === 2) return 'or-discord-preview-card__rank or-discord-preview-card__rank--silver';
  if (rank === 3) return 'or-discord-preview-card__rank or-discord-preview-card__rank--bronze';
  return 'or-discord-preview-card__rank';
}

export default function DiscordPreviewCard({
  models,
  maxCount = 5,
  botName,
  botAvatarUrl,
  phases = [],
  rankings = {},
}: Props) {
  const [variant, setVariant] = useState<Variant>('precios');
  const meta = VARIANT_META[variant];
  const displayBotName = botName || 'Ressy Bot';

  const now = new Date();
  const time = `${now.getHours().toString().padStart(2, '0')}:${now
    .getMinutes()
    .toString()
    .padStart(2, '0')}`;

  const cheapest = useMemo(() => {
    return [...models]
      .filter((m) => {
        const p = m.pricing_prompt_per_mtok;
        const c = m.pricing_completion_per_mtok;
        return p != null && c != null && p >= 0 && c >= 0;
      })
      .sort((a, b) => {
        const ap = (a.pricing_prompt_per_mtok ?? 0) + (a.pricing_completion_per_mtok ?? 0);
        const bp = (b.pricing_prompt_per_mtok ?? 0) + (b.pricing_completion_per_mtok ?? 0);
        return ap - bp;
      })
      .slice(0, Math.min(maxCount, 5));
  }, [models, maxCount]);

  const orchestratorRanking = rankings['orchestrator']?.entries ?? [];
  const orchestratorPhase = phases.find((p) => p.slug === 'orchestrator');

  return (
    <div className="or-discord-preview-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-3 flex-shrink-0 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="material-symbols-outlined text-secondary text-[22px] flex-shrink-0"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            visibility
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none truncate">
            Vista Previa Discord
          </span>
        </div>
        <div className="or-discord-preview-card__variants flex-shrink-0">
          {(Object.keys(VARIANT_META) as Variant[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setVariant(v)}
              className={
                'or-discord-preview-card__variant ' + (variant === v ? 'is-active' : '')
              }
            >
              <span className="material-symbols-outlined text-[12px]">
                {VARIANT_META[v].icon}
              </span>
              <span className="hidden sm:inline">{VARIANT_META[v].label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="or-discord-preview-card__mock rounded-xl p-3 font-sans shadow-xl flex-1 min-h-0 overflow-y-auto animate-openrouter-card-enter">
        <div className="flex gap-2">
          <div className="w-9 h-9 rounded-full flex-shrink-0 overflow-hidden bg-secondary flex items-center justify-center">
            {botAvatarUrl ? (
              <img
                src={botAvatarUrl}
                alt={displayBotName}
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="material-symbols-outlined text-white text-[20px]">smart_toy</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-1 flex-wrap">
              <span className="font-bold text-white text-sm hover:underline cursor-pointer">
                {displayBotName}
              </span>
              <span className="bg-[#5865f2] text-[9px] px-1 rounded-sm text-white font-bold uppercase py-0.5">
                BOT
              </span>
              <span className="text-[11px] text-[#949ba4] ml-1">Hoy a las {time}</span>
            </div>

            <div
              className="or-discord-preview-card__embed"
              style={{ borderLeft: `4px solid ${meta.color}` }}
              key={variant}
            >
              <div className="p-2.5">
                <p className="font-bold text-white text-[13px] leading-tight mb-1.5">
                  {meta.title}
                </p>

                {variant === 'precios' && (
                  <>
                    <div className="text-xs text-[#dbdee1] mb-2">
                      Top {cheapest.length} modelos de texto más baratos por prompt token
                    </div>
                    {cheapest.length === 0 ? (
                      <div className="text-[11px] text-[#949ba4] italic">
                        Sin datos cacheados. Ejecuta una actualización del catálogo.
                      </div>
                    ) : (
                      <div className="space-y-0">
                        {cheapest.map((m, idx) => (
                          <div
                            key={m.id}
                            className="or-discord-preview-card__row animate-openrouter-row-fade"
                            style={{ animationDelay: `${idx * 50}ms` }}
                          >
                            <div className="flex items-center min-w-0 flex-1">
                              <span className={getRankClass(idx + 1)}>{idx + 1}</span>
                              <div className="min-w-0 flex-1">
                                <p className="text-[12px] font-bold text-white truncate">
                                  {m.name || m.id.split('/').pop()}
                                </p>
                                <p className="text-[10px] text-[#949ba4] truncate">{m.id}</p>
                              </div>
                            </div>
                            <div className="text-right flex-shrink-0">
                              <p className="text-[12px] text-white font-mono">
                                {formatPrice(m.pricing_prompt_per_mtok)} /{' '}
                                {formatPrice(m.pricing_completion_per_mtok)}
                              </p>
                              <p className="text-[9px] text-[#949ba4]">
                                $/Mtok prompt · completion
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="mt-2 text-[10px] text-[#949ba4] flex justify-between">
                      <span>/precios-openrouter</span>
                      <span>Actualizado {time}</span>
                    </div>
                  </>
                )}

                {variant === 'ranking' && (
                  <>
                    <div className="text-xs text-[#dbdee1] mb-2">
                      Fase: <b>{orchestratorPhase?.label ?? 'Orquestador'}</b>
                      {' · '}
                      pesos: IFBench, AA Intelligence, τ²-Telecom, BFCL, features
                    </div>
                    {orchestratorRanking.length === 0 ? (
                      <div className="text-[11px] text-[#949ba4] italic">
                        Sin datos de ranking aún. Espera al próximo scrape AA + BFCL.
                      </div>
                    ) : (
                      <div className="space-y-0">
                        {orchestratorRanking.slice(0, 5).map((entry, idx) => (
                          <div
                            key={`${entry.model_id}-${entry.rank}`}
                            className="or-discord-preview-card__row animate-openrouter-row-fade"
                            style={{ animationDelay: `${idx * 50}ms` }}
                          >
                            <div className="flex items-center min-w-0 flex-1">
                              <span className={getRankClass(entry.rank)}>{entry.rank}</span>
                              <div className="min-w-0 flex-1">
                                <p className="text-[12px] font-bold text-white truncate">
                                  {entry.model_name || entry.model_id}
                                </p>
                                <p className="text-[10px] text-[#949ba4] truncate">
                                  Score {entry.score.toFixed(3)}
                                </p>
                              </div>
                            </div>
                            <div className="text-right flex-shrink-0">
                              <p className="text-[12px] text-white font-mono">
                                {formatPrice(entry.pricing_prompt_per_mtok)} /{' '}
                                {formatPrice(entry.pricing_completion_per_mtok)}
                              </p>
                              <p className="text-[9px] text-[#949ba4]">$/Mtok</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="mt-2 text-[10px] text-[#949ba4] flex justify-between">
                      <span>Embed bi-semanal automático</span>
                      <span>Bot SDD · {time}</span>
                    </div>
                  </>
                )}

                {variant === 'weekly' && (
                  <>
                    <div className="text-xs text-[#dbdee1] mb-2">
                      Resumen semanal del catálogo. Variaciones de precios y modelos nuevos.
                    </div>
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <div className="or-discord-preview-card__field">
                        <span className="or-discord-preview-card__field-name">
                          Modelos en caché
                        </span>
                        <span className="or-discord-preview-card__field-value">
                          {models.length}
                        </span>
                      </div>
                      <div className="or-discord-preview-card__field">
                        <span className="or-discord-preview-card__field-name">
                          Modelos nuevos
                        </span>
                        <span className="or-discord-preview-card__field-value">
                          {Math.max(0, Math.floor(models.length * 0.03))}
                        </span>
                      </div>
                      <div className="or-discord-preview-card__field">
                        <span className="or-discord-preview-card__field-name">
                          Modelo más barato
                        </span>
                        <span className="or-discord-preview-card__field-value">
                          {cheapest[0]?.name ?? cheapest[0]?.id ?? '—'}
                        </span>
                      </div>
                      <div className="or-discord-preview-card__field">
                        <span className="or-discord-preview-card__field-name">
                          Bajaron de precio
                        </span>
                        <span className="or-discord-preview-card__field-value">
                          {Math.max(0, Math.floor(models.length * 0.015))}
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 text-[10px] text-[#949ba4] flex justify-between">
                      <span>Reporte enviado cada lunes</span>
                      <span>Bot OpenRouter · {time}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
