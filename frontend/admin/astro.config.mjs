// @ts-check
import { defineConfig, fontProviders } from 'astro/config';

/*
  Painel interno. Este build NUNCA vai para o Vercel — ele é servido só dentro
  da tailnet. É por isso que admin/ e public/ são projetos separados: com um
  `dist/` único, publicar o público publicaria o painel junto.
*/
export default defineConfig({
  publicDir: 'static',

  build: {
    format: 'file',
  },

  fonts: [
    {
      provider: fontProviders.fontsource(),
      name: 'Poppins',
      cssVariable: '--font-display',
      weights: [400, 600, 700],
      styles: ['normal'],
      subsets: ['latin', 'latin-ext'],
      fallbacks: ['ui-sans-serif', 'system-ui', 'sans-serif'],
    },
    {
      provider: fontProviders.fontsource(),
      name: 'Inter',
      cssVariable: '--font-body',
      weights: [400, 500, 600],
      styles: ['normal'],
      subsets: ['latin', 'latin-ext'],
      fallbacks: ['ui-sans-serif', 'system-ui', 'sans-serif'],
    },
  ],
});
