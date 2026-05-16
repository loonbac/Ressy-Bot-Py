export interface DistroVisual {
  color: string;
  icon: string;
}

export const DISTRO_META: Record<string, DistroVisual> = {
  ubuntu: { color: '#E95420', icon: 'verified_user' },
  debian: { color: '#A81D33', icon: 'terminal' },
  fedora: { color: '#294172', icon: 'potted_plant' },
  'rocky-linux': { color: '#10B981', icon: 'mountain_flag' },
  linuxmint: { color: '#69B53F', icon: 'eco' },
  linux: { color: '#4F4446', icon: 'settings_suggest' },
  opensuse: { color: '#73BA25', icon: 'pets' },
  almalinux: { color: '#0F4266', icon: 'shield_lock' },
  'alpine-linux': { color: '#0D597F', icon: 'landscape' },
  'pop-os': { color: '#48B9C7', icon: 'rocket_launch' },
  rhel: { color: '#EE0000', icon: 'workspace_premium' },
  arch: { color: '#1793D1', icon: 'memory_alt' },
  cachyos: { color: '#7C5BFA', icon: 'bolt' },
  bazzite: { color: '#FF6B9D', icon: 'sports_esports' },
  manjaro: { color: '#34BE5B', icon: 'forest' },
  endeavouros: { color: '#7F3FBF', icon: 'public' },
};

export const ROLLING_SLUGS: ReadonlySet<string> = new Set([
  'arch',
  'cachyos',
  'bazzite',
  'manjaro',
  'endeavouros',
]);

export function metaFor(slug: string): DistroVisual {
  return DISTRO_META[slug] ?? { color: '#75565e', icon: 'memory' };
}

export function statusLabel(active: number, expiringSoon: number, expired: number): string {
  if (expired > 0) return 'Expirada';
  if (expiringSoon > 0) return 'Próxima EOL';
  if (active > 0) return 'Activa';
  return 'Sin datos';
}
