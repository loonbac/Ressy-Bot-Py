import AnimatedSaveButton, { type SaveState } from './AnimatedSaveButton';
import AnimatedTestButton, { type TestState } from './AnimatedTestButton';

export interface TestFeedback {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

interface Props {
  saveState: SaveState;
  testState: TestState;
  testCount: number;
  testFeedback: TestFeedback | null;
  onSave: () => void;
  onTest: () => void;
  onTestCountChange: (n: number) => void;
}

export default function FooterActions({
  saveState,
  testState,
  testCount,
  testFeedback,
  onSave,
  onTest,
  onTestCountChange,
}: Props) {
  return (
    <div className="flex flex-wrap justify-end items-center gap-3 py-3 px-5 bg-surface-container-low/40 rounded-xl border border-outline-variant/10">
      {testFeedback && (
        <div
          key={testFeedback.nonce}
          className="animate-toast-in flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-container-highest border border-outline-variant/30 shadow-sm"
        >
          <span
            className={`material-symbols-outlined text-[18px] ${
              testFeedback.kind === 'success' ? 'text-green-500' : 'text-error'
            }`}
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {testFeedback.kind === 'success' ? 'check_circle' : 'error'}
          </span>
          <span className="text-sm text-on-surface">{testFeedback.text}</span>
        </div>
      )}
      <div className="flex items-center gap-2 bg-surface-container-low/60 border border-outline-variant/30 rounded-lg pl-3 pr-1.5 py-1">
        <label className="text-label-sm text-on-surface-variant uppercase font-bold tracking-wide">
          Últimos
        </label>
        <input
          type="number"
          min={1}
          max={10}
          value={testCount}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            if (Number.isNaN(v)) {
              onTestCountChange(1);
            } else {
              onTestCountChange(Math.max(1, Math.min(10, v)));
            }
          }}
          className="w-12 bg-transparent text-center text-sm font-body-md outline-none focus:ring-2 focus:ring-secondary/30 rounded-md py-1 text-on-surface"
        />
        <span className="text-label-sm text-on-surface-variant pr-1">video(s)</span>
      </div>
      <AnimatedTestButton state={testState} onClick={onTest} />
      <AnimatedSaveButton saveState={saveState} onSave={onSave} />
    </div>
  );
}
