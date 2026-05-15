import type { YouTubeConfig } from '@/api/youtube';

interface Props {
  config: YouTubeConfig;
  onCallbackUrlChange: (v: string) => void;
  onApiKeyChange: (v: string) => void;
}

export default function ConnectionCard({
  config,
  onCallbackUrlChange,
  onApiKeyChange,
}: Props) {
  return (
    <div className="bg-surface-container-lowest/60 backdrop-blur-md rounded-xl p-4 border border-white/40 shadow-sm">
      <h3 className="font-headline-md text-headline-md mb-3 flex items-center gap-2">
        <span className="material-symbols-outlined text-secondary text-[20px]">link</span>
        Conexión
      </h3>
      <div className="space-y-3">
        <div>
          <label className="block text-label-sm text-primary font-bold uppercase mb-1">
            URL de Callback
          </label>
          <input
            type="url"
            className={`w-full bg-surface-container-low border rounded-lg py-2 px-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none transition-all text-on-surface ${
              !config.callback_url ? 'border-error/60' : 'border-outline-variant/30'
            }`}
            placeholder="https://tu-dominio.ngrok-free.app"
            value={config.callback_url}
            onChange={(e) => onCallbackUrlChange(e.target.value)}
          />
          <p className="text-xs text-error/80 mt-1 flex items-start gap-1">
            <span className="material-symbols-outlined text-[16px] mt-0.5" style={{fontVariationSettings: "'FILL' 1"}}>warning</span>
            URL pública obligatoria. Sin esto el plugin no recibe notificaciones de YouTube.
          </p>
        </div>
        <div>
          <label className="block text-label-sm text-primary font-bold uppercase mb-1">
            Google API Key
          </label>
          <input
            type="password"
            className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg py-2 px-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none transition-all text-on-surface"
            placeholder="AIzaSy..."
            value={config.google_api_key}
            onChange={(e) => onApiKeyChange(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
