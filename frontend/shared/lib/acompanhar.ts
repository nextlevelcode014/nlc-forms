/*
  Acompanhamento — o lado do cliente.

  Sem chave de admin: a credencial é o código, como no rastreio dos Correios.
  Por isso tudo aqui é de leitura curada ou escrita restrita — a API decide o
  que sai, e esta camada só transporta.
*/

import { api } from './api';
import type { Servico } from './triagem';

export interface EventoPublico {
  titulo: string;
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
  /** Título do último evento visível. Null enquanto nada aconteceu. */
  estado: string | null;
  orcamento: { total: number; validade: string | null } | null;
  historico: EventoPublico[];
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
