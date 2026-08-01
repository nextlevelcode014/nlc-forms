/*
  Cliente HTTP da API do nlc-forms.

  A base vem de `PUBLIC_API_BASE` (variável de build do Astro) em vez de ficar
  escrita à mão em cada página, como era antes. Trocar o endereço da tailnet
  passou a ser mexer no `.env`, não em oito arquivos.
*/

export const API_BASE: string =
  import.meta.env.PUBLIC_API_BASE ?? 'https://nextlevelcode.tail181a66.ts.net:8000';

export type Servico = 'suporte' | 'seguranca' | 'desenvolvimento';

/** Erro com o status HTTP preservado, para a UI decidir a mensagem. */
export class ErroApi extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ErroApi';
  }
}

interface OpcoesApi extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /** Chave de admin. Só o projeto admin passa isto. */
  adminKey?: string | null;
}

/**
 * Faz a requisição e já normaliza o erro: o backend responde `{detail: "..."}`
 * no corpo, e é essa mensagem que interessa mostrar — não o status cru.
 */
export async function api<T = unknown>(caminho: string, opcoes: OpcoesApi = {}): Promise<T> {
  const { body, adminKey, headers, ...resto } = opcoes;

  const res = await fetch(`${API_BASE}${caminho}`, {
    ...resto,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(adminKey ? { 'X-Admin-Key': adminKey } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (!res.ok) {
    const detalhe = await res
      .json()
      .then((d) => (d as { detail?: string }).detail)
      .catch(() => null);
    throw new ErroApi(detalhe ?? `Erro ${res.status}`, res.status);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Baixa um PDF autenticado. `fetch` + blob porque `<a download>` não manda header. */
export async function baixarPdf(caminho: string, nomeArquivo: string, adminKey: string) {
  const res = await fetch(`${API_BASE}${caminho}`, { headers: { 'X-Admin-Key': adminKey } });
  if (!res.ok) throw new ErroApi(`Erro ${res.status}`, res.status);

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nomeArquivo;
  a.click();
  // Sem o revoke o blob fica preso na memória da aba até o reload.
  URL.revokeObjectURL(url);
}
