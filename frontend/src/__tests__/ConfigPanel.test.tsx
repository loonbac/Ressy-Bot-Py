import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ConfigPanel from '@/components/ConfigPanel';
import { ConfigResponse } from '@/types';

const mockConfigs: ConfigResponse[] = [
  { key: 'version', value: '1.0.0', updated_at: '2024-01-01T00:00:00Z' },
  { key: 'bot_prefix', value: '!', updated_at: '2024-01-01T00:00:00Z' },
];

describe('ConfigPanel', () => {
  it('renders the list of configs from props', () => {
    render(<ConfigPanel configs={mockConfigs} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText('version')).toBeInTheDocument();
    expect(screen.getByLabelText('bot_prefix')).toBeInTheDocument();
  });

  it('shows empty state when no configs', () => {
    render(<ConfigPanel configs={[]} onUpdate={vi.fn()} />);
    expect(screen.getByText('No configuration values yet')).toBeInTheDocument();
  });

  it('calls onUpdate when clicking save', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<ConfigPanel configs={mockConfigs} onUpdate={onUpdate} />);
    const input = screen.getByLabelText('version') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '2.0.0' } });
    fireEvent.click(screen.getAllByText('Save')[0]);
    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalledWith('version', '2.0.0');
    });
  });

  it('shows error if onUpdate fails', async () => {
    const onUpdate = vi.fn().mockRejectedValue(new Error('Bad request'));
    render(<ConfigPanel configs={mockConfigs} onUpdate={onUpdate} />);
    fireEvent.click(screen.getAllByText('Save')[0]);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Bad request');
    });
  });

  it('shows loading state while saving', async () => {
    const onUpdate = vi.fn(
      () => new Promise<void>((resolve) => setTimeout(resolve, 100))
    );
    render(<ConfigPanel configs={mockConfigs} onUpdate={onUpdate} />);
    fireEvent.click(screen.getAllByText('Save')[0]);
    expect(screen.getByText('Saving…')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('Saving…')).not.toBeInTheDocument();
    });
  });
});
