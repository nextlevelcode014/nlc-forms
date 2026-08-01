/*
  Sessão do admin.

  A chave fica só em memória, de propósito: nada de localStorage. Persistir uma
  chave de admin em disco do navegador significa que qualquer script na página —
  ou quem sentar na máquina depois — a lê. O custo é digitar de novo a cada
  recarga, e para uma ferramenta interna esse é o lado certo da troca.
*/

import { api, ErroApi } from './api';

let chave: string | null = null;

export function chaveAtual(): string {
  if (!chave) throw new Error('Sessão de admin não iniciada.');
  return chave;
}

export function temSessao(): boolean {
  return chave !== null;
}

/**
 * Valida a chave numa chamada barata ao catálogo — o backend não tem rota de
 * login, então autenticar é fazer uma requisição autenticada qualquer e ver
 * se volta 401.
 */
export async function entrar(candidata: string): Promise<void> {
  await api('/admin/catalogo?servico=suporte', { adminKey: candidata });
  chave = candidata;
}

/** Encerra a sessão. A chave sai da memória; nada foi gravado em disco. */
export function encerrar(): void {
  chave = null;
}

export function traduzirErro(erro: unknown, contexto: string): string {
  if (erro instanceof ErroApi) {
    if (erro.status === 401) return 'Chave de admin inválida ou sessão expirada.';
    return `${contexto}: ${erro.message}`;
  }
  return 'Não foi possível conectar à API.';
}
