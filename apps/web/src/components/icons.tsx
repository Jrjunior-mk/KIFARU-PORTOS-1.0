/** Inline SVG icon set (no icon dependency). All icons are 24x24 stroke icons, currentColor. */
import type { SVGProps } from 'react';

export type IconName =
  | 'dashboard' | 'scale' | 'truck' | 'steering' | 'box' | 'warehouse' | 'cube' | 'shield' | 'registry' | 'flask' | 'settings'
  | 'bell' | 'menu' | 'close' | 'chevron' | 'logout' | 'search' | 'check' | 'alert' | 'info' | 'token' | 'ruler' | 'port' | 'quarry' | 'road' | 'lane' | 'static' | 'anchor' | 'database' | 'link';

const PATHS: Record<IconName, string> = {
  dashboard: 'M3 13h8V3H3zM13 21h8V11h-8zM13 3v5h8V3zM3 21h8v-5H3z',
  scale: 'M12 3v18M5 7h14M7 7l-3 7a3 3 0 0 0 6 0zM17 7l-3 7a3 3 0 0 0 6 0zM8 21h8',
  truck: 'M3 7h11v9H3zM14 10h4l3 3v3h-7zM6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  steering: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 12h6M15 12h6M12 15v6',
  box: 'M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8',
  warehouse: 'M3 21V9l9-5 9 5v12M7 21v-6h10v6M10 21v-6',
  cube: 'M12 2l8 4.5v9L12 20l-8-4.5v-9zM12 11l8-4.5M12 11L4 6.5M12 11v9',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4',
  registry: 'M6 3h9l4 4v14H6zM14 3v5h5M9 13h6M9 17h6M9 9h2',
  flask: 'M9 3h6M10 3v6L4 20a1 1 0 0 0 .9 1.5h14.2A1 1 0 0 0 20 20l-6-11V3M7 15h10',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0',
  menu: 'M4 6h16M4 12h16M4 18h16',
  close: 'M6 6l12 12M18 6L6 18',
  chevron: 'M9 6l6 6-6 6',
  logout: 'M10 17l5-5-5-5M15 12H3M21 4v16',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
  check: 'M20 6L9 17l-5-5',
  alert: 'M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16v-4M12 8h.01',
  token: 'M12 2l3 3h4v4l3 3-3 3v4h-4l-3 3-3-3H5v-4l-3-3 3-3V5h4zM9 12l2 2 4-4',
  ruler: 'M3 17l14-14 4 4L7 21zM7 13l2 2M10 10l2 2M13 7l2 2',
  port: 'M12 3v8M8 7h8M12 11a6 6 0 0 1-6 6M12 11a6 6 0 0 0 6 6M3 21c3-2 6-2 9 0 3-2 6-2 9 0',
  quarry: 'M3 20l5-9 4 6 3-4 6 7zM14 4l3 3-3 3-3-3z',
  road: 'M9 3L6 21M15 3l3 18M12 6v2M12 11v2M12 16v2',
  lane: 'M3 12h18M3 7h4M3 17h4M17 7h4M17 17h4M12 4v16',
  static: 'M4 20h16M6 20V9h12v11M9 9V4h6v5M9 14h6',
  anchor: 'M12 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 8v13M5 12H2a10 10 0 0 0 20 0h-3M8 12H5M19 12h-3',
  database: 'M12 8c5 0 9-1.3 9-3s-4-3-9-3-9 1.3-9 3 4 3 9 3zM3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12c0 1.7 4 3 9 3s9-1.3 9-3',
  link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.5 1.5M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.5-1.5',
};

export function Icon({ name, size = 18, className = '', ...rest }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className} {...rest}>
      <path d={PATHS[name]} />
    </svg>
  );
}
