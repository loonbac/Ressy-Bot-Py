import AnimatedSaveButton, { type SaveState } from './AnimatedSaveButton';
import AnimatedTestButton, { type TestState } from './AnimatedTestButton';
import './FooterActions.css';
import './animations.css';

export type { SaveState, TestState };

interface Feedback {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

interface Props {
  saveState: SaveState;
  testState: TestState;
  feedback: Feedback | null;
  onSave: () => void;
  onTest: () => void;
}

export default function FooterActions({
  saveState,
  testState,
  feedback,
  onSave,
  onTest,
}: Props) {
  return (
    <div className="welcome-footer flex flex-wrap justify-end items-center gap-3 py-2.5 px-4 rounded-xl flex-shrink-0">
      {feedback && (
        <div
          key={feedback.nonce}
          className="welcome-footer__feedback animate-welcome-toast-slide flex items-center gap-2 px-3 py-1.5 rounded-full shadow-sm"
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

      <AnimatedTestButton state={testState} onClick={onTest} />
      <AnimatedSaveButton state={saveState} onClick={onSave} />
    </div>
  );
}
