// @ts-check
import { defineConfig, fontProviders } from 'astro/config';

/*
  Painel interno. Este build NUNCA vai para o Vercel — ele é servido só dentro
  da tailnet. É por isso que admin/ e public/ são projetos separados: com um
  `dist/` único, publicar o público publicaria o painel junto.
*/
export default defineConfig({
  publicDir: 'static',

  // A porta não é preferência: ela precisa estar no ALLOWED_ORIGINS da API,
  // senão o navegador barra por CORS antes da requisição sair. Sem esta linha o
  // `astro dev` usava a padrão 4321 — a mesma do projeto público — e rodando os
  // dois juntos o segundo caía em 4322, que não está liberado. O README já
  // documentava 9080; agora o comando cumpre sozinho.
  server: {
    port: 9080,
  },

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
