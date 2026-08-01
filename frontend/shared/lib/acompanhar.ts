/*
  Acompanhamento — o lado do cliente.

  Sem chave de admin: a credencial é o código, como no rastreio dos Correios.
  Por isso tudo aqui é de leitura curada ou escrita restrita — a API decide o
  que sai, e esta camada só transporta.
*/

import { api } from './api';
import type { Servico } from './triagem';

export interface EventoPublico {
  passo: string;
  rotulo: string;
  detalhe: string;
  origem: 'sistema' | 'admin' | 'cliente';
  criado_em: string;
}

export interface Acompanhamento {
  codigo: string;
  servico: Servico;
  servico_rotulo: string;
  cliente: string;
  aberto_em: string;
  status: string;
  status_rotulo: string;
  orcamento: { total: number; validade: string | null } | null;
  historico: EventoPublico[];
  /** A ordem das etapas vem do backend: a página não mantém a própria cópia. */
  passos: { passo: string; rotulo: string }[];
}

export function buscarAcompanhamento(codigo: string) {
  return api<Acompanhamento>(`/acompanhar/${encodeURIComponent(codigo)}`);
}

export function enviarMensagem(codigo: string, mensagem: string) {
  return api<{ ok: boolean }>(`/acompanhar/${encodeURIComponent(codigo)}/mensagem`, {
    method: 'POST',
    body: { mensagem },
  });
}

export function atualizarContato(codigo: string, dados: { nome?: string; telefone?: string }) {
  return api<{ ok: boolean }>(`/acompanhar/${encodeURIComponent(codigo)}/contato`, {
    method: 'POST',
    body: dados,
  });
}

/**
 * Onde o atendimento está na régua de etapas.
 *
 * Devolve -1 quando o status atual não é uma etapa da régua (uma mensagem, por
 * exemplo) — aí a barra não se move, em vez de saltar para o começo.
 */
export function posicaoDoPasso(dados: Acompanhamento): number {
  return dados.passos.findIndex((p) => p.passo === dados.status);
}
