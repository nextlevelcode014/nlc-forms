/*
  Schema do nlc-forms — fonte única da verdade.

  Mudou de "um registro por formulário" para "uma pasta por cliente": o cliente
  é criado por você, antes de qualquer formulário, e cada triagem é um documento
  dentro da pasta dele. O mesmo Fábio com dois notebooks diferentes são duas
  triagens no mesmo cliente, não dois Fábios.

  Quem amarra a triagem ao cliente é o TOKEN, não o e-mail digitado. Você já sabe
  para quem está mandando o link, então um erro de digitação no formulário não
  cria mais uma pasta fantasma.

  Ao mudar algo aqui: `bun run generate` na pasta backend/, e o .sql sai em
  drizzle/migrations/. As consultas do Python são SQL puro e NÃO acompanham
  automaticamente — renomear coluna aqui exige achar os SELECTs lá.
*/
import { sql } from 'drizzle-orm';
import { index, integer, real, sqliteTable, text, uniqueIndex } from 'drizzle-orm/sqlite-core';

// Datas em TEXT ISO 8601, UTC sem offset — ver app/tempo.py. SQLite não tem
// tipo de data, e trocar por INTEGER agora quebraria toda comparação existente.
const agora = () => text().notNull();

/* ── Clientes ──────────────────────────────────────────────
   A pasta. Existe antes do primeiro formulário e sobrevive a todos eles. */
export const clientes = sqliteTable(
  'clientes',
  {
    id: integer().primaryKey({ autoIncrement: true }),
    nome: text().notNull(),
    // Guardado já normalizado (minúsculo, sem espaço nas pontas): é chave de
    // identidade, e comparar só na consulta deixaria `Fabio@Email.com ` e
    // `fabio@email.com` virarem dois clientes.
    email: text().notNull(),
    telefone: text().default(''),
    // Suas anotações sobre a pessoa — não sobre um atendimento. Nunca sai em PDF
    // nem na página de acompanhamento.
    notas: text().default(''),
    criado_em: agora(),
    atualizado_em: agora(),
  },
  (t) => [uniqueIndex('idx_clientes_email').on(t.email)],
);

/* ── Tokens ────────────────────────────────────────────────
   Link de uso único. Agora carrega o cliente: é o que garante que a triagem
   caia na pasta certa, independente do que for digitado no formulário. */
export const tokens = sqliteTable(
  'tokens',
  {
    token: text().primaryKey(),
    cliente_id: integer()
      .notNull()
      .references(() => clientes.id, { onDelete: 'cascade' }),
    servico: text().notNull(),
    criado_em: agora(),
    expira_em: text().notNull(),
    usado: integer().notNull().default(0),
    usado_em: text(),
    nota: text().default(''),
  },
  (t) => [index('idx_tokens_cliente').on(t.cliente_id)],
);

/* ── Triagens ──────────────────────────────────────────────
   As perguntas de cada serviço, iguais ao que já eram. O que saiu foram nome,
   e-mail e telefone: contato agora é propriedade do cliente, não uma cópia
   dentro de cada formulário — que era o que deixava o mesmo cliente com três
   grafias diferentes do próprio nome. */
const colunasComuns = {
  id: integer().primaryKey({ autoIncrement: true }),
  codigo: text().notNull(),
  cliente_id: integer()
    .notNull()
    .references(() => clientes.id, { onDelete: 'cascade' }),
  token: text(),
  criado_em: agora(),
};

export const triagemSuporte = sqliteTable(
  'triagem_suporte',
  {
    ...colunasComuns,
    problema: text().notNull(),
    quando: text().notNull(),
    causa: text().default(''),
    tentou: text().default(''),
    marca: text().notNull(),
    modelo: text().default(''),
    sistema: text().notNull(),
    idade: text().default(''),
    armazenamento: text().default(''),
    ram: text().default(''),
    tem_backup: text().notNull(),
    programas: text().notNull(),
    modalidade: text().notNull(),
    observacoes: text().default(''),
  },
  (t) => [
    uniqueIndex('idx_triagem_suporte_codigo').on(t.codigo),
    index('idx_triagem_suporte_cliente').on(t.cliente_id),
  ],
);

export const triagemSeguranca = sqliteTable(
  'triagem_seguranca',
  {
    ...colunasComuns,
    perfil: text().notNull(),
    dispositivos: text().notNull(),
    servicos: text().notNull(),
    preocupacao: text().notNull(),
    incidente: text().notNull(),
    incidente_desc: text().default(''),
    usa_2fa: text().notNull(),
    usa_gerenciador: text().notNull(),
    tem_backup: text().notNull(),
    modalidade: text().notNull(),
    observacoes: text().default(''),
  },
  (t) => [
    uniqueIndex('idx_triagem_seguranca_codigo').on(t.codigo),
    index('idx_triagem_seguranca_cliente').on(t.cliente_id),
  ],
);

export const triagemDesenvolvimento = sqliteTable(
  'triagem_desenvolvimento',
  {
    ...colunasComuns,
    tipo_cliente: text().notNull(),
    tipo_projeto: text().notNull(),
    descricao: text().notNull(),
    tem_referencia: text().notNull(),
    referencia_url: text().default(''),
    prazo: text().notNull(),
    orcamento: text().notNull(),
    ja_tem_algo: text().notNull(),
    ja_tem_desc: text().default(''),
    stack_preferida: text().default(''),
    observacoes: text().default(''),
  },
  (t) => [
    uniqueIndex('idx_triagem_desenvolvimento_codigo').on(t.codigo),
    index('idx_triagem_desenvolvimento_cliente').on(t.cliente_id),
  ],
);

/* ── Catálogo e execução ───────────────────────────────────
   Inalterados. */
export const catalogoItens = sqliteTable('catalogo_itens', {
  id: integer().primaryKey({ autoIncrement: true }),
  servico: text().notNull(),
  nome: text().notNull(),
  valor: real().notNull(),
  ativo: integer().notNull().default(1),
});

export const execucao = sqliteTable(
  'execucao',
  {
    id: integer().primaryKey({ autoIncrement: true }),
    codigo: text().notNull(),
    servico: text().notNull(),
    criado_em: agora(),
    atualizado_em: text(),
    // `status` saiu daqui: o estado é sempre o título do último evento visível
    // do histórico. Guardar uma cópia foi o que fez a régua do cliente ficar
    // parada enquanto o atendimento andava — um caminho gravava o evento e não
    // o status. Derivado não diverge, e apagar um evento devolve o anterior.
    diagnostico: text().default(''),
    servicos_realizados: text().default(''),
    recomendacoes: text().default(''),
    // Nunca sai em PDF nem na página do cliente.
    observacoes_internas: text().default(''),
    itens_json: text().default('[]'),
    valor_total: real().default(0),
    data_atendimento: text(),
    validade_orcamento: text(),
    pdf_gerado_em: text(),
  },
  (t) => [uniqueIndex('idx_execucao_codigo').on(t.codigo)],
);

/* ── Histórico ─────────────────────────────────────────────
   A linha do tempo que o cliente vê no acompanhamento, no espírito do rastreio
   dos Correios: cada linha é um evento com hora.

   Um `status` sozinho não serve para isso — ele diz onde o caso está, não como
   chegou lá, e é justamente o "aguardando a peça chegar" que faz o cliente
   mandar mensagem perguntando. Eventos automáticos entram nos pontos que o
   código já conhece; os manuais são os que você escreve. */
export const historico = sqliteTable(
  'historico',
  {
    id: integer().primaryKey({ autoIncrement: true }),
    codigo: text().notNull(),
    // Escrito por você, na hora. Não há lista de etapas predefinida: a fita da
    // página do cliente começa vazia e só ganha marcas conforme os eventos
    // acontecem. Sugestões de título vêm do que já foi usado (titulos_usados).
    titulo: text().notNull(),
    // Complemento opcional, mostrado abaixo do título.
    detalhe: text().default(''),
    // 'sistema' | 'admin' | 'cliente' — a página distingue o que veio de você
    // do que o próprio cliente escreveu.
    origem: text().notNull().default('sistema'),
    // false esconde o evento do cliente sem apagá-lo do seu histórico.
    visivel_cliente: integer().notNull().default(1),
    criado_em: agora(),
  },
  (t) => [index('idx_historico_codigo').on(t.codigo)],
);

/* ── Relatórios técnicos ───────────────────────────────────
   Guarda o Markdown, não o PDF: o documento é renderizado sob demanda, então
   relatório antigo sempre sai no template atual da marca. */
export const relatoriosMd = sqliteTable(
  'relatorios_md',
  {
    id: integer().primaryKey({ autoIncrement: true }),
    codigo: text().notNull(),
    titulo: text().notNull(),
    subtitulo: text().default(''),
    descricao: text().default(''),
    versao: text().default(''),
    markdown: text().notNull(),
    criado_em: agora(),
    atualizado_em: agora(),
  },
  (t) => [index('idx_relatorios_md_codigo').on(t.codigo)],
);

// Silencia o aviso de import não usado quando nenhuma coluna precisa de sql``.
export const _ = sql;
