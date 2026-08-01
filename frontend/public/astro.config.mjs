// @ts-check
import { defineConfig, fontProviders } from 'astro/config';

export default defineConfig({
  site: 'https://support.nextlevelcode.pro',

  // O diretório de assets estáticos do Astro chama-se `public` por padrão, e
  // este projeto JÁ se chama public/ — `public/public/` seria confuso.
  publicDir: 'static',

  // Explícita mesmo sendo a padrão do Astro: a porta faz parte do contrato com
  // o ALLOWED_ORIGINS da API, e um padrão que muda de versão levaria o CORS
  // junto. O painel usa 9080 pelo mesmo motivo.
  server: {
    port: 4321,
  },

  build: {
    // `file` mantém as URLs que já foram enviadas a clientes:
    // /triagem-suporte.html continua existindo. Com o padrão `directory` elas
    // virariam /triagem-suporte/ e todo link de token já distribuído quebraria.
    format: 'file',
  },

  // Fonts API nativa: baixa as fontes no build e serve do próprio domínio.
  // Nenhuma requisição do visitante vai para o Google — sem vazamento de IP e
  // sem depender de CDN de terceiros.
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
