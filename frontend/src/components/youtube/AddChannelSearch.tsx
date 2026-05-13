import { useEffect, useRef, useState } from 'react';
import {
  type YouTubeSearchResult,
  searchYouTubeChannels,
  getProxiedThumbnailUrl,
} from '@/api/youtube';

interface Props {
  onSelect: (result: YouTubeSearchResult) => Promise<void> | void;
}

export default function AddChannelSearch({ onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<YouTubeSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    setError(null);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!value.trim()) {
      setResults([]);
      return;
    }

    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const r = await searchYouTubeChannels(value.trim());
        setResults(r);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al buscar');
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 400);
  };

  const handlePick = async (result: YouTubeSearchResult) => {
    setSearching(true);
    try {
      await onSelect(result);
      setQuery('');
      setResults([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al agregar canal');
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="relative">
      <div className="flex items-center gap-2 mb-2">
        <span className="material-symbols-outlined text-[18px] text-secondary">add_link</span>
        <span className="text-label-sm text-on-surface-variant font-bold uppercase">
          Añadir Canal
        </span>
      </div>
      <input
        className="w-full bg-transparent border-b-2 border-outline-variant/30 focus:border-secondary outline-none py-2 px-1 transition-all duration-300 text-sm font-body-md placeholder:text-outline-variant"
        placeholder="Buscar canal de YouTube..."
        type="text"
        value={query}
        onChange={handleChange}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setResults([]);
        }}
      />

      {results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full bg-surface-container-lowest border border-outline-variant/20 rounded-xl shadow-xl overflow-hidden max-h-48 overflow-y-auto">
          {results.map((result) => (
            <button
              key={result.channel_id}
              onClick={() => handlePick(result)}
              className="w-full flex items-center gap-3 p-3 hover:bg-primary-container/20 transition-colors text-left border-b border-outline-variant/10 last:border-b-0"
            >
              <img
                src={getProxiedThumbnailUrl(result.thumbnail)}
                alt={result.channel_name}
                className="w-8 h-8 rounded-full border border-outline-variant/20 flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-on-surface text-sm truncate">
                  {result.channel_name}
                </p>
                <p className="text-label-sm text-tertiary truncate">{result.description}</p>
              </div>
              <span className="material-symbols-outlined text-secondary text-[20px]">
                add_circle
              </span>
            </button>
          ))}
        </div>
      )}

      {searching && results.length === 0 && query.trim() && (
        <div className="absolute z-50 mt-1 w-full bg-surface-container-lowest border border-outline-variant/20 rounded-xl shadow-xl p-3 text-center text-tertiary text-sm">
          <span className="material-symbols-outlined animate-spin inline-block text-[18px]">
            progress_activity
          </span>
          <span className="ml-2">Buscando...</span>
        </div>
      )}

      {error && <p className="text-error text-xs mt-1">{error}</p>}
    </div>
  );
}
