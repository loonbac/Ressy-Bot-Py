import { useEffect, useRef } from 'react';

interface Petal {
  x: number;
  y: number;
  size: number;
  rotation: number;
  rotationSpeed: number;
  speedX: number;
  speedY: number;
  opacity: number;
  swayPhase: number;
  swayAmplitude: number;
  color: string;
}

const PETAL_COLORS = [
  'rgba(183, 19, 41, 0.35)',   // secondary
  'rgba(117, 86, 94, 0.3)',    // primary
  'rgba(255, 217, 225, 0.5)',  // primary-fixed
  'rgba(227, 189, 197, 0.4)',  // primary-fixed-dim
  'rgba(218, 50, 63, 0.25)',   // secondary-container
];

function createPetal(canvasWidth: number): Petal {
  return {
    x: Math.random() * canvasWidth,
    y: -20 - Math.random() * 60,
    size: 6 + Math.random() * 10,
    rotation: Math.random() * 360,
    rotationSpeed: (Math.random() - 0.5) * 2,
    speedX: (Math.random() - 0.5) * 0.4,
    speedY: 0.3 + Math.random() * 0.6,
    opacity: 0.3 + Math.random() * 0.5,
    swayPhase: Math.random() * Math.PI * 2,
    swayAmplitude: 0.5 + Math.random() * 1.5,
    color: PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)],
  };
}

function drawPetal(ctx: CanvasRenderingContext2D, petal: Petal) {
  ctx.save();
  ctx.translate(petal.x, petal.y);
  ctx.rotate((petal.rotation * Math.PI) / 180);
  ctx.globalAlpha = petal.opacity;
  ctx.fillStyle = petal.color;

  // Draw a petal shape using bezier curves
  const s = petal.size;
  ctx.beginPath();
  ctx.moveTo(0, -s);
  ctx.bezierCurveTo(s * 0.8, -s * 0.6, s * 0.6, s * 0.3, 0, s * 0.5);
  ctx.bezierCurveTo(-s * 0.6, s * 0.3, -s * 0.8, -s * 0.6, 0, -s);
  ctx.fill();

  // Add a subtle vein line
  ctx.strokeStyle = petal.color;
  ctx.globalAlpha = petal.opacity * 0.3;
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.moveTo(0, -s * 0.8);
  ctx.quadraticCurveTo(s * 0.1, 0, 0, s * 0.4);
  ctx.stroke();

  ctx.restore();
}

export default function SakuraPetals() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const petalsRef = useRef<Petal[]>([]);
  const animFrameRef = useRef<number>(0);
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const MAX_PETALS = 25;

    // Seed initial petals spread across the canvas
    petalsRef.current = [];
    for (let i = 0; i < MAX_PETALS; i++) {
      const p = createPetal(canvas.width);
      p.y = Math.random() * canvas.height;
      petalsRef.current.push(p);
    }

    const animate = () => {
      if (!canvas || !ctx) return;
      timeRef.current += 0.016;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Spawn new petals if needed
      if (petalsRef.current.length < MAX_PETALS && Math.random() < 0.05) {
        petalsRef.current.push(createPetal(canvas.width));
      }

      petalsRef.current = petalsRef.current.filter((p) => {
        // Update position
        p.swayPhase += 0.02;
        p.x += p.speedX + Math.sin(p.swayPhase) * p.swayAmplitude;
        p.y += p.speedY;
        p.rotation += p.rotationSpeed;

        // Draw
        drawPetal(ctx, p);

        // Remove if off screen
        return p.y < canvas.height + 30;
      });

      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      window.removeEventListener('resize', resizeCanvas);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-[1]"
      aria-hidden="true"
    />
  );
}
