-- Converte as chaves do vocabulário antigo em texto que o cliente possa ler.
--
-- Até a migração anterior, `historico.passo` guardava chaves de um enum
-- (`aguardando_peca`) e a página traduzia para o rótulo na hora. Sem o enum, o
-- título É o que aparece na tela — e "aguardando_peca" não é português.
--
-- Migração de conteúdo, escrita à mão: o drizzle-kit gera diff de estrutura.
UPDATE historico SET titulo = 'Triagem recebida'         WHERE titulo = 'recebido';
--> statement-breakpoint
UPDATE historico SET titulo = 'Em análise'               WHERE titulo = 'em_analise';
--> statement-breakpoint
UPDATE historico SET titulo = 'Orçamento enviado'        WHERE titulo = 'orcamento_enviado';
--> statement-breakpoint
UPDATE historico SET titulo = 'Aguardando sua aprovação' WHERE titulo = 'aguardando_aprovacao';
--> statement-breakpoint
UPDATE historico SET titulo = 'Aguardando peça'          WHERE titulo = 'aguardando_peca';
--> statement-breakpoint
UPDATE historico SET titulo = 'Em execução'              WHERE titulo = 'em_execucao';
--> statement-breakpoint
UPDATE historico SET titulo = 'Concluído'                WHERE titulo = 'concluido';
--> statement-breakpoint
UPDATE historico SET titulo = 'Mensagem enviada'         WHERE titulo = 'mensagem_cliente';
--> statement-breakpoint
-- Eventos de texto livre guardavam 'manual' como chave e o texto no detalhe.
-- Agora o texto é o próprio título.
UPDATE historico SET titulo = detalhe, detalhe = ''
 WHERE titulo = 'manual' AND TRIM(COALESCE(detalhe, '')) != '';
