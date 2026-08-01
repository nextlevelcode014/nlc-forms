CREATE TABLE `catalogo_itens` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`servico` text NOT NULL,
	`nome` text NOT NULL,
	`valor` real NOT NULL,
	`ativo` integer DEFAULT 1 NOT NULL
);
--> statement-breakpoint
CREATE TABLE `clientes` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`nome` text NOT NULL,
	`email` text NOT NULL,
	`telefone` text DEFAULT '',
	`notas` text DEFAULT '',
	`criado_em` text NOT NULL,
	`atualizado_em` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_clientes_email` ON `clientes` (`email`);--> statement-breakpoint
CREATE TABLE `execucao` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`codigo` text NOT NULL,
	`servico` text NOT NULL,
	`criado_em` text NOT NULL,
	`atualizado_em` text,
	`status` text DEFAULT 'recebido' NOT NULL,
	`diagnostico` text DEFAULT '',
	`servicos_realizados` text DEFAULT '',
	`recomendacoes` text DEFAULT '',
	`observacoes_internas` text DEFAULT '',
	`itens_json` text DEFAULT '[]',
	`valor_total` real DEFAULT 0,
	`data_atendimento` text,
	`validade_orcamento` text,
	`pdf_gerado_em` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_execucao_codigo` ON `execucao` (`codigo`);--> statement-breakpoint
CREATE TABLE `historico` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`codigo` text NOT NULL,
	`passo` text NOT NULL,
	`detalhe` text DEFAULT '',
	`origem` text DEFAULT 'sistema' NOT NULL,
	`visivel_cliente` integer DEFAULT 1 NOT NULL,
	`criado_em` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_historico_codigo` ON `historico` (`codigo`);--> statement-breakpoint
CREATE TABLE `relatorios_md` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`codigo` text NOT NULL,
	`titulo` text NOT NULL,
	`subtitulo` text DEFAULT '',
	`descricao` text DEFAULT '',
	`versao` text DEFAULT '',
	`markdown` text NOT NULL,
	`criado_em` text NOT NULL,
	`atualizado_em` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_relatorios_md_codigo` ON `relatorios_md` (`codigo`);--> statement-breakpoint
CREATE TABLE `tokens` (
	`token` text PRIMARY KEY NOT NULL,
	`cliente_id` integer NOT NULL,
	`servico` text NOT NULL,
	`criado_em` text NOT NULL,
	`expira_em` text NOT NULL,
	`usado` integer DEFAULT 0 NOT NULL,
	`usado_em` text,
	`nota` text DEFAULT '',
	FOREIGN KEY (`cliente_id`) REFERENCES `clientes`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `idx_tokens_cliente` ON `tokens` (`cliente_id`);--> statement-breakpoint
CREATE TABLE `triagem_desenvolvimento` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`codigo` text NOT NULL,
	`cliente_id` integer NOT NULL,
	`token` text,
	`criado_em` text NOT NULL,
	`tipo_cliente` text NOT NULL,
	`tipo_projeto` text NOT NULL,
	`descricao` text NOT NULL,
	`tem_referencia` text NOT NULL,
	`referencia_url` text DEFAULT '',
	`prazo` text NOT NULL,
	`orcamento` text NOT NULL,
	`ja_tem_algo` text NOT NULL,
	`ja_tem_desc` text DEFAULT '',
	`stack_preferida` text DEFAULT '',
	`observacoes` text DEFAULT '',
	FOREIGN KEY (`cliente_id`) REFERENCES `clientes`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_triagem_desenvolvimento_codigo` ON `triagem_desenvolvimento` (`codigo`);--> statement-breakpoint
CREATE INDEX `idx_triagem_desenvolvimento_cliente` ON `triagem_desenvolvimento` (`cliente_id`);--> statement-breakpoint
CREATE TABLE `triagem_seguranca` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`codigo` text NOT NULL,
	`cliente_id` integer NOT NULL,
	`token` text,
	`criado_em` text NOT NULL,
	`perfil` text NOT NULL,
	`dispositivos` text NOT NULL,
	`servicos` text NOT NULL,
	`preocupacao` text NOT NULL,
	`incidente` text NOT NULL,
	`incidente_desc` text DEFAULT '',
	`usa_2fa` text NOT NULL,
	`usa_gerenciador` text NOT NULL,
	`tem_backup` text NOT NULL,
	`modalidade` text NOT NULL,
	`observacoes` text DEFAULT '',
	FOREIGN KEY (`cliente_id`) REFERENCES `clientes`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_triagem_seguranca_codigo` ON `triagem_seguranca` (`codigo`);--> statement-breakpoint
CREATE INDEX `idx_triagem_seguranca_cliente` ON `triagem_seguranca` (`cliente_id`);--> statement-breakpoint
CREATE TABLE `triagem_suporte` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`codigo` text NOT NULL,
	`cliente_id` integer NOT NULL,
	`token` text,
	`criado_em` text NOT NULL,
	`problema` text NOT NULL,
	`quando` text NOT NULL,
	`causa` text DEFAULT '',
	`tentou` text DEFAULT '',
	`marca` text NOT NULL,
	`modelo` text DEFAULT '',
	`sistema` text NOT NULL,
	`idade` text DEFAULT '',
	`armazenamento` text DEFAULT '',
	`ram` text DEFAULT '',
	`tem_backup` text NOT NULL,
	`programas` text NOT NULL,
	`modalidade` text NOT NULL,
	`observacoes` text DEFAULT '',
	FOREIGN KEY (`cliente_id`) REFERENCES `clientes`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_triagem_suporte_codigo` ON `triagem_suporte` (`codigo`);--> statement-breakpoint
CREATE INDEX `idx_triagem_suporte_cliente` ON `triagem_suporte` (`cliente_id`);