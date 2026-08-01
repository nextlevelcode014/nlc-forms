/*
  Sugestões de título para os eventos do atendimento.

  Substitui a lista fixa de etapas. Não é um vocabulário decretado: é o que você
  já escreveu antes, oferecido como atalho. A lista fixa prometia um caminho que
  nem todo atendimento percorre — "aguardando peça" não existe num projeto de
  desenvolvimento — e ainda engessava quem atende.
*/

import { api } from './api';

// Uma requisição por sessão. A lista muda pouco e o rate limit da API é de 10
// por janela; buscar a cada abertura de cliente torraria a cota à toa.
let cache: Promise<string[]> | null = null;

export function carregarTitulos(adminKey: string): Promise<string[]> {
  cache ??= api<{ titulos: string[] }>('/admin/titulos', { adminKey }).then((r) => r.titulos);
  return cache;
}

/** Esquece o cache para um título recém-criado aparecer na próxima sugestão. */
export function esquecerTitulos(): void {
  cache = null;
}
