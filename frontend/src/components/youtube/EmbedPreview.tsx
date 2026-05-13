import { useEffect, useState } from 'react';

interface Props {
  announcementMessage: string;
}

export default function EmbedPreview({ announcementMessage }: Props) {
  const [EmbedVisualizer, setEmbedVisualizer] = useState<any>(null);
  const [cssLoaded, setCssLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mod = await import('embed-visualizer');
        if (!cancelled) setEmbedVisualizer(() => mod.EmbedVisualizer);
        await import('embed-visualizer/dist/index.css');
        if (!cancelled) setCssLoaded(true);
      } catch (e) {
        console.error('Failed to load embed visualizer:', e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!EmbedVisualizer || !cssLoaded) {
    return (
      <div className="bg-surface-container-low rounded-xl p-4 text-tertiary text-sm text-center">
        Cargando vista previa...
      </div>
    );
  }

  const content = announcementMessage.replace('{canal}', 'Canal de Ejemplo') || undefined;

  return (
    <div className="bg-discord rounded-xl overflow-hidden" style={{ maxWidth: 520 }}>
      <EmbedVisualizer
        embed={{
          content,
          embed: {
            color: 0xff0000,
            author: { name: 'Canal de Ejemplo', url: 'https://youtube.com' },
            title: 'Título del Nuevo Video',
            url: 'https://youtube.com/watch?v=dQw4w9WgXcQ',
            description: 'Nuevo video publicado en YouTube',
            image: { url: 'https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg' },
            footer: { text: 'YouTube' },
            timestamp: new Date().toISOString(),
          },
        }}
        onError={(e: unknown) => console.error(e)}
      />
    </div>
  );
}
