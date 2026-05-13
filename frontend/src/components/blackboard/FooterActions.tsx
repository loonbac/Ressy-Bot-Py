import AnimatedSaveButton, { type SaveState } from './AnimatedSaveButton';
import AnimatedScrapeButton, { type ScrapeState } from './AnimatedScrapeButton';
import AnimatedSendPendingButton, { type SendState } from './AnimatedSendPendingButton';
import './FooterActions.css';

export type { SaveState, ScrapeState, SendState };

interface Feedback {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

interface Props {
  saveState: SaveState;
  scrapeState: ScrapeState;
  sendState: SendState;
  feedback: Feedback | null;
  onSave: () => void;
  onScrape: () => void;
  onSendPending: () => void;
}

export default function FooterActions({
  saveState,
  scrapeState,
  sendState,
  feedback,
  onSave,
  onScrape,
  onSendPending,
}: Props) {
  return (
    <div className="bb-footer flex flex-wrap justify-end items-center gap-3 py-2.5 px-4 rounded-xl flex-shrink-0">
      {feedback && (
        <div
          key={feedback.nonce}
          className="bb-footer__feedback animate-toast-in flex items-center gap-2 px-3 py-1.5 rounded-full shadow-sm"
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

      <AnimatedSendPendingButton state={sendState} onClick={onSendPending} />
      <AnimatedScrapeButton state={scrapeState} onClick={onScrape} />
      <AnimatedSaveButton state={saveState} onClick={onSave} />
    </div>
  );
}
