import { useEffect, useState } from 'react';
import './animations.css';

interface Props {
  trigger: number; // changing nonce re-fires the burst
  colors?: string[];
  count?: number;
}

const DEFAULT_COLORS = ['#da323f', '#f7cfd8', '#5865f2', '#4ade80', '#f59e0b', '#a78bfa'];

interface Particle {
  id: number;
  tx: number;
  ty: number;
  color: string;
  delay: number;
}

export default function ConfettiBurst({
  trigger,
  colors = DEFAULT_COLORS,
  count = 14,
}: Props) {
  const [particles, setParticles] = useState<Particle[]>([]);

  useEffect(() => {
    if (trigger === 0) return;
    const fresh: Particle[] = Array.from({ length: count }, (_, i) => {
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4;
      const dist = 50 + Math.random() * 60;
      return {
        id: trigger * 1000 + i,
        tx: Math.cos(angle) * dist,
        ty: Math.sin(angle) * dist - 20,
        color: colors[i % colors.length],
        delay: Math.random() * 80,
      };
    });
    setParticles(fresh);
    const timer = window.setTimeout(() => setParticles([]), 1100);
    return () => window.clearTimeout(timer);
  }, [trigger, count, colors]);

  if (particles.length === 0) return null;

  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      {particles.map((p) => (
        <span
          key={p.id}
          className="bb-confetti"
          style={
            {
              '--tx': `${p.tx}px`,
              '--ty': `${p.ty}px`,
              backgroundColor: p.color,
              animationDelay: `${p.delay}ms`,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}
