/*
  Os passos do atendimento — um vocabulário só.

  Antes existiam dois: o painel oferecia `pendente`/`em_andamento`/`concluido`
  num STATUS_LABEL escrito à mão aqui no frontend, e a régua do cliente esperava
  os PASSOS definidos em app/historico.py. Só `concluido` coincidia, então mudar
  o status para "Em andamento" não movia a régua nem gerava evento — o cliente
  via o atendimento parado enquanto ele andava.

  A lista agora vem do backend, que é quem também valida a gravação. Passo novo
  em app/historico.py aparece no seletor, no filtro e na régua sem tocar aqui.
*/

import { api } from './api';

export interface Passo {
  passo: string;
  rotulo: string;
}

// Uma requisição por sessão: a lista não muda enquanto a página está aberta, e
// o rate limit da API é de 10 por janela — buscar a cada render torraria a cota
// só para desenhar rótulo de tabela.
let cache: Promise<Passo[]> | null = null;

export function carregarPassos(adminKey: string): Promise<Passo[]> {
  cache ??= api<{ passos: Passo[] }>('/admin/passos', { adminKey }).then((r) => r.passos);
  return cache;
}

/** Rótulo legível de um status. Devolve o próprio valor se for desconhecido. */
export function rotuloDe(passos: Passo[], status: string | null): string {
  if (!status) return 'Sem atendimento';
  return passos.find((p) => p.passo === status)?.rotulo ?? status;
}
