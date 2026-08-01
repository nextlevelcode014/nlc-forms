import { defineConfig } from 'drizzle-kit';

/*
  O Drizzle aqui é ferramenta de autoria, não de runtime.

  Ele não roda em produção: `drizzle-kit generate` compara o schema.ts com o
  histórico e escreve um .sql em drizzle/migrations/, que é versionado no git.
  Quem aplica é o app/migrar.py, em Python, no boot do container — assim o Pi
  não precisa de Node nem bun para subir a API.

  A consequência a não esquecer: o schema.ts é a fonte da verdade, mas as
  consultas continuam em SQL puro no Python. Renomear uma coluna aqui não
  reescreve o SELECT lá.
*/
export default defineConfig({
  dialect: 'sqlite',
  schema: './drizzle/schema.ts',
  out: './drizzle/migrations',
});
