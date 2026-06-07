import './base.css';
import './FooterActions.css';

export type SaveState = 'idle' | 'saving' | 'success' | 'error';

export interface Feedback {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

interface Props {
  saveState: SaveState;
  feedback: Feedback | null;
  dirty: boolean;
  onSave: () => void;
  onDiscard: () => void;
}

export default function FooterActions({ saveState, feedback, dirty, onSave, onDiscard }: Props) {
  const saving = saveState === 'saving';
  return (
    <div className="flex items-center justify-between gap-3 flex-shrink-0">
      <div className="min-h-[1.5rem]">
        {feedback && (
          <span
            key={feedback.nonce}
            className={
              'videos-feedback animate-videos-toast-slide ' +
              (feedback.kind === 'success' ? 'videos-feedback--ok' : 'videos-feedback--err')
            }
          >
            <span className="material-symbols-outlined text-[16px]">
              {feedback.kind === 'success' ? 'check_circle' : 'error'}
            </span>
            {feedback.text}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onDiscard}
          disabled={!dirty || saving}
          className="videos-btn-ghost px-4 py-2 text-sm disabled:opacity-40"
        >
          Descartar
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={!dirty || saving}
          className={
            'videos-btn-primary px-5 py-2 text-sm flex items-center gap-1.5 ' +
            (saveState === 'success' ? 'animate-videos-pop' : '')
          }
        >
          {saving ? (
            <span className="material-symbols-outlined text-[18px] animate-videos-spin">
              progress_activity
            </span>
          ) : saveState === 'success' ? (
            <span className="material-symbols-outlined text-[18px]">check</span>
          ) : (
            <span className="material-symbols-outlined text-[18px]">save</span>
          )}
          {saving ? 'Guardando…' : 'Guardar cambios'}
        </button>
      </div>
    </div>
  );
}
