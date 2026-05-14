# Layout Fixes — 2026-05-13

## Problemas
- TopAppBar no alineado con el contenido principal (faltaba max-width container)
- Página YouTube: calc-based sizing causaba scroll issues
- Sin modularización de componentes

## Cambios

### DashboardLayout.tsx
- TopAppBar ahora envuelto en `max-w-container-max mx-auto px-margin-desktop`
- Alineado con el contenido principal

### YouTubeConfig.tsx + componentes split
- Layout cambiado a fixed positioning: `top-20 bottom-0 left-64 right-0`
- Grid rows: auto / 1fr / auto (header, contenido scrollable, footer)
- Columnas pasaron de grid 12-col a flexbox con flex-[7]/flex-[5]
- Nuevos componentes: ChannelsListCard, FooterActions, MessageSettingsCard,
  FiltersCard, ConnectionCard (cada uno en frontend/src/components/youtube/)
