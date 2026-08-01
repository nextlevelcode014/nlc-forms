-- Unifica o vocabulário de status com os passos da linha do tempo.
--
-- O painel gravava `pendente`, `em_andamento` e `concluido`, enquanto a régua
-- de acompanhamento do cliente esperava os PASSOS de app/historico.py. Só
-- `concluido` existia nos dois lados, então mudar o status para "Em andamento"
-- não mexia a régua nem criava evento — ela simplesmente não avançava.
--
-- Migração de dados, não de schema: por isso é `--custom`, escrita à mão. O
-- drizzle-kit gera diff de estrutura; conteúdo é conosco.
UPDATE execucao SET status = 'recebido'    WHERE status = 'pendente';
--> statement-breakpoint
UPDATE execucao SET status = 'em_execucao' WHERE status = 'em_andamento';
