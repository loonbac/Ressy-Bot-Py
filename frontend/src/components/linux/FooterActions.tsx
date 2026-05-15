import AnimatedSaveButton, { type SaveState } from './AnimatedSaveButton';
import './FooterActions.css';
import './animations.css';

export type { SaveState };

interface Feedback {
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

export default function FooterActions({
  saveState,
  feedback,
  dirty,
  onSave,
  onDiscard,
}: Props) {
  return (
    <div className="linux-footer flex flex-wrap justify-end items-center gap-3 py-2.5 px-4 rounded-xl flex-shrink-0">
      {feedback && (
        <div
          key={feedback.nonce}
          className="linux-footer__feedback animate-linux-toast-slide flex items-center gap-2 px-3 py-1.5 rounded-full shadow-sm"
        >
          <span
            className={`material-symbols-outlined text-[18px] ${
              feedback.kind === 'success' ? 'text-green-500' : 'text-error'
            }`}
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {feedback.kind === 'success' ? 'check_circle' : 'error'}
          </span>
          <span className="text-sm text-on-surface">{feedback.text}</span>
        </div>
      )}

      <button
        type="button"
        onClick={onDiscard}
        disabled={!dirty || saveState === 'saving'}
        className="linux-footer__discard text-sm font-bold px-4 py-2 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Descartar cambios
      </button>

      <AnimatedSaveButton state={saveState} onClick={onSave} disabled={!dirty} />
    </div>
  );
}
