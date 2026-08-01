/*
  Clientes — a pasta.

  Fica no shared/ porque três telas do painel precisam do mesmo tipo e da mesma
  busca: gerar token, listar pastas e abrir a ficha. Deixar cada uma com a sua
  cópia foi como o contato do cliente acabou existindo em três grafias.
*/

import { api } from './api';
import type { Servico } from './triagem';

export interface Cliente {
  id: number;
  nome: string;
  email: string;
  telefone: string;
  notas: string;
  criado_em: string;
  atualizado_em: string;
}

/** O que a listagem acrescenta: o resumo do que há dentro da pasta. */
export interface ClienteComResumo extends Cliente {
  triagens: number;
  servicos_distintos: number;
  servicos: Servico[];
  ultima_triagem: string | null;
}

export interface TriagemDaPasta {
  codigo: string;
  servico: Servico;
  criado_em: string;
  status: string | null;
  valor_total: number | null;
  data_atendimento: string | null;
}

export function listarClientes(adminKey: string, search = '') {
  const query = search ? `?search=${encodeURIComponent(search)}` : '';
  return api<{ clientes: ClienteComResumo[]; total: number }>(`/admin/clientes${query}`, {
    adminKey,
  });
}

export function buscarCliente(adminKey: string, id: number) {
  return api<{ cliente: Cliente; triagens: TriagemDaPasta[]; servicos: Servico[] }>(
    `/admin/clientes/${id}`,
    { adminKey },
  );
}

export function criarCliente(
  adminKey: string,
  dados: { nome: string; email: string; telefone?: string; notas?: string },
) {
  return api<Cliente>('/admin/clientes', { method: 'POST', adminKey, body: dados });
}

export function atualizarCliente(
  adminKey: string,
  id: number,
  dados: { nome: string; email: string; telefone?: string; notas?: string },
) {
  return api<Cliente>(`/admin/clientes/${id}`, { method: 'PUT', adminKey, body: dados });
}

export function excluirCliente(adminKey: string, id: number) {
  return api<{ ok: boolean; triagens_removidas: number }>(`/admin/clientes/${id}`, {
    method: 'DELETE',
    adminKey,
  });
}

/** Uma linha "Nome <email>" para listas e seletores. */
export function identidade(c: Cliente): string {
  return `${c.nome} <${c.email}>`;
}
