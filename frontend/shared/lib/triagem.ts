/*
  Definição dos formulários de triagem.

  Antes cada serviço tinha uma página HTML própria de ~780 linhas, das quais
  ~700 eram idênticas. Aqui fica só o que de fato difere — os campos — e a
  renderização é a mesma para os três.

  Os `nome` batem 1:1 com as colunas de `triagem_suporte`, `triagem_seguranca` e
  `triagem_desenvolvimento` (backend/app/database.py). Renomear um campo aqui sem
  renomear a coluna quebra o INSERT em silêncio, porque o backend monta o INSERT
  a partir das chaves do JSON.

  O admin também lê estes rótulos para exibir a triagem — assim não existem duas
  listas de labels para divergirem.
*/

import type { Servico } from './api';

// Reexportado para que quem consome os formulários não precise importar de dois
// módulos só para nomear o serviço.
export type { Servico };

export type TipoCampo = 'texto' | 'email' | 'tel' | 'textarea' | 'select' | 'radio';

export interface Campo {
  nome: string;
  rotulo: string;
  tipo: TipoCampo;
  obrigatorio?: boolean;
  placeholder?: string;
  opcoes?: string[];
  /** Ocupa metade da linha, emparelhado com o campo seguinte. */
  meia?: boolean;
}

export interface Secao {
  titulo: string;
  campos: Campo[];
}

export interface Formulario {
  servico: Servico;
  titulo: string;
  descricao: string;
  secoes: Secao[];
}

/** Bloco de contato — idêntico nos três serviços. */
function contato(placeholderNome = 'Seu nome completo'): Secao {
  return {
    titulo: 'Contato',
    campos: [
      { nome: 'nome', rotulo: 'Nome', tipo: 'texto', obrigatorio: true, placeholder: placeholderNome, meia: true },
      { nome: 'email', rotulo: 'E-mail', tipo: 'email', obrigatorio: true, placeholder: 'seu@email.com', meia: true },
      { nome: 'telefone', rotulo: 'WhatsApp', tipo: 'tel', placeholder: '(11) 99999-9999' },
    ],
  };
}

const MODALIDADE: Campo = {
  nome: 'modalidade',
  rotulo: 'Preferência de modalidade',
  tipo: 'radio',
  obrigatorio: true,
  opcoes: ['Remoto', 'Presencial', 'Qualquer um'],
};

const OBSERVACOES: Campo = {
  nome: 'observacoes',
  rotulo: 'Observações adicionais',
  tipo: 'textarea',
  placeholder: 'Algo mais que queira informar...',
};

export const SUPORTE: Formulario = {
  servico: 'suporte',
  titulo: 'suporte técnico',
  descricao:
    'Preencha as informações abaixo para que eu possa entender seu problema antes do atendimento.',
  secoes: [
    contato(),
    {
      titulo: 'Problema',
      campos: [
        {
          nome: 'problema',
          rotulo: 'Qual é o problema principal?',
          tipo: 'textarea',
          obrigatorio: true,
          placeholder: 'Descreva o que está acontecendo com suas próprias palavras...',
        },
        {
          nome: 'quando',
          rotulo: 'Quando o problema começou?',
          tipo: 'select',
          obrigatorio: true,
          meia: true,
          opcoes: [
            'Hoje',
            'Nos últimos dias',
            'Nas últimas semanas',
            'Há mais de um mês',
            'Desde que tenho o equipamento',
          ],
        },
        {
          nome: 'causa',
          rotulo: 'Aconteceu algo antes do problema?',
          tipo: 'texto',
          meia: true,
          placeholder: 'Ex: atualização, queda, instalação...',
        },
        {
          nome: 'tentou',
          rotulo: 'Já tentou resolver de alguma forma?',
          tipo: 'texto',
          placeholder: 'Ex: reiniciei, desinstalei um programa...',
        },
      ],
    },
    {
      titulo: 'Equipamento',
      campos: [
        { nome: 'marca', rotulo: 'Marca', tipo: 'texto', obrigatorio: true, meia: true, placeholder: 'Ex: Dell, Lenovo, Samsung...' },
        { nome: 'modelo', rotulo: 'Modelo', tipo: 'texto', meia: true, placeholder: 'Ex: Inspiron 15 3000' },
        {
          nome: 'sistema',
          rotulo: 'Sistema operacional',
          tipo: 'select',
          obrigatorio: true,
          meia: true,
          opcoes: [
            'Windows 11',
            'Windows 10',
            'Windows (não sei a versão)',
            'Ubuntu / Linux Mint',
            'Outro Linux',
            'Não sei',
          ],
        },
        {
          nome: 'idade',
          rotulo: 'Idade aproximada do equipamento',
          tipo: 'select',
          meia: true,
          opcoes: ['Menos de 1 ano', '1 a 3 anos', '3 a 5 anos', 'Mais de 5 anos', 'Não sei'],
        },
        {
          nome: 'armazenamento',
          rotulo: 'Tipo de armazenamento',
          tipo: 'select',
          meia: true,
          opcoes: ['SSD', 'HD (mecânico)', 'Não sei'],
        },
        {
          nome: 'ram',
          rotulo: 'Memória RAM',
          tipo: 'select',
          meia: true,
          opcoes: ['4 GB', '8 GB', '16 GB ou mais', 'Não sei'],
        },
      ],
    },
    {
      titulo: 'Dados e prioridades',
      campos: [
        {
          nome: 'tem_backup',
          rotulo: 'Tem dados importantes sem backup?',
          tipo: 'radio',
          obrigatorio: true,
          opcoes: ['Sim', 'Não', 'Não sei'],
        },
        {
          nome: 'programas',
          rotulo: 'Quais programas são essenciais para você?',
          tipo: 'texto',
          obrigatorio: true,
          placeholder: 'Ex: Excel, Chrome, programa da empresa X...',
        },
      ],
    },
    { titulo: 'Atendimento', campos: [MODALIDADE, OBSERVACOES] },
  ],
};

export const SEGURANCA: Formulario = {
  servico: 'seguranca',
  titulo: 'segurança & privacidade',
  descricao:
    'Preencha as informações abaixo para que eu possa entender seu contexto digital antes da assessoria.',
  secoes: [
    contato(),
    {
      titulo: 'Perfil digital',
      campos: [
        {
          nome: 'perfil',
          rotulo: 'Como você usa seus dispositivos no dia a dia?',
          tipo: 'select',
          obrigatorio: true,
          opcoes: [
            'Uso pessoal',
            'Uso profissional',
            'Ambos — pessoal e profissional',
            'Pequeno negócio / autônomo',
          ],
        },
        {
          nome: 'dispositivos',
          rotulo: 'Quais dispositivos você usa?',
          tipo: 'texto',
          obrigatorio: true,
          placeholder: 'Ex: notebook Windows, iPhone, tablet Android...',
        },
        {
          nome: 'servicos',
          rotulo: 'Quais são seus serviços/contas mais importantes?',
          tipo: 'texto',
          obrigatorio: true,
          placeholder: 'Ex: Gmail, banco, Instagram, e-mail do trabalho...',
        },
      ],
    },
    {
      titulo: 'Preocupações e histórico',
      campos: [
        {
          nome: 'preocupacao',
          rotulo: 'O que mais te preocupa em relação à sua segurança digital?',
          tipo: 'textarea',
          obrigatorio: true,
          placeholder:
            'Ex: golpes, exposição de dados, invasão de contas, privacidade em redes sociais...',
        },
        {
          nome: 'incidente',
          rotulo: 'Já teve alguma conta invadida ou situação suspeita?',
          tipo: 'radio',
          obrigatorio: true,
          opcoes: ['Sim', 'Não', 'Não sei'],
        },
        {
          nome: 'incidente_desc',
          rotulo: 'Se sim, pode descrever brevemente?',
          tipo: 'texto',
          placeholder: 'O que aconteceu...',
        },
      ],
    },
    {
      titulo: 'Hábitos atuais',
      campos: [
        {
          nome: 'usa_2fa',
          rotulo: 'Você já usa autenticação em dois fatores (2FA)?',
          tipo: 'radio',
          obrigatorio: true,
          opcoes: ['Sim, em algumas contas', 'Não uso', 'Não sei o que é'],
        },
        {
          nome: 'usa_gerenciador',
          rotulo: 'Você usa gerenciador de senhas?',
          tipo: 'radio',
          obrigatorio: true,
          opcoes: ['Sim', 'Não', 'Não sei o que é'],
        },
        {
          nome: 'tem_backup',
          rotulo: 'Você faz backup regularmente?',
          tipo: 'radio',
          obrigatorio: true,
          opcoes: ['Sim', 'Não', 'Às vezes'],
        },
      ],
    },
    { titulo: 'Atendimento', campos: [MODALIDADE, OBSERVACOES] },
  ],
};

export const DESENVOLVIMENTO: Formulario = {
  servico: 'desenvolvimento',
  titulo: 'dev & automação',
  descricao:
    'Preencha as informações abaixo para que eu possa entender seu projeto antes de conversarmos.',
  secoes: [
    contato('Seu nome ou nome da empresa'),
    {
      titulo: 'Sobre o projeto',
      campos: [
        {
          nome: 'tipo_cliente',
          rotulo: 'Você está falando como:',
          tipo: 'select',
          obrigatorio: true,
          opcoes: [
            'Pessoa física',
            'Autônomo / profissional liberal',
            'Pequeno negócio',
            'Empresa de médio/grande porte',
          ],
        },
        {
          nome: 'tipo_projeto',
          rotulo: 'Que tipo de solução você precisa?',
          tipo: 'select',
          obrigatorio: true,
          opcoes: [
            'Automação de processo/tarefa',
            'Aplicação web (sistema, dashboard, painel)',
            'API ou integração entre sistemas',
            'Site institucional ou landing page',
            'Não sei ainda — quero conversar',
          ],
        },
        {
          nome: 'descricao',
          rotulo: 'Descreva o que você precisa',
          tipo: 'textarea',
          obrigatorio: true,
          placeholder:
            'Conte com suas palavras o que você imagina ou o problema que precisa resolver...',
        },
      ],
    },
    {
      titulo: 'Referências e contexto',
      campos: [
        {
          nome: 'tem_referencia',
          rotulo: 'Tem alguma referência ou exemplo do que você quer?',
          tipo: 'radio',
          obrigatorio: true,
          opcoes: ['Sim', 'Não'],
        },
        {
          nome: 'referencia_url',
          rotulo: 'Link ou descrição da referência',
          tipo: 'texto',
          placeholder: 'URL de um site/app parecido, ou breve descrição...',
        },
        {
          nome: 'ja_tem_algo',
          rotulo: 'Você já tem algo construído (site, planilha, sistema antigo)?',
          tipo: 'radio',
          obrigatorio: true,
          opcoes: ['Sim', 'Não, é do zero'],
        },
        {
          nome: 'ja_tem_desc',
          rotulo: 'Se sim, descreva brevemente',
          tipo: 'texto',
          placeholder: 'Ex: planilha em Excel, sistema antigo em PHP...',
        },
      ],
    },
    {
      titulo: 'Prazo e orçamento',
      campos: [
        {
          nome: 'prazo',
          rotulo: 'Qual o prazo desejado?',
          tipo: 'select',
          obrigatorio: true,
          opcoes: [
            'Urgente — menos de 2 semanas',
            'Até 1 mês',
            '1 a 3 meses',
            'Sem pressa — ainda planejando',
          ],
        },
        {
          nome: 'orcamento',
          rotulo: 'Qual faixa de orçamento você tem em mente?',
          tipo: 'select',
          obrigatorio: true,
          opcoes: [
            'Ainda não defini',
            'Até R$ 1.000',
            'R$ 1.000 a R$ 3.000',
            'R$ 3.000 a R$ 7.000',
            'Acima de R$ 7.000',
          ],
        },
        {
          nome: 'stack_preferida',
          rotulo: 'Tem preferência de tecnologia?',
          tipo: 'texto',
          placeholder: 'Ex: nenhuma preferência, ou já uso Python...',
        },
      ],
    },
    { titulo: 'Detalhes finais', campos: [OBSERVACOES] },
  ],
};

export const FORMULARIOS: Record<Servico, Formulario> = {
  suporte: SUPORTE,
  seguranca: SEGURANCA,
  desenvolvimento: DESENVOLVIMENTO,
};

export const ROTULO_SERVICO: Record<Servico, string> = {
  suporte: 'Suporte Técnico',
  seguranca: 'Segurança & Privacidade',
  desenvolvimento: 'Dev & Automação',
};

/** Mapa campo -> rótulo longo (o mesmo texto que o cliente leu no formulário). */
export function rotulosDe(servico: Servico): Record<string, string> {
  const mapa: Record<string, string> = {};
  for (const secao of FORMULARIOS[servico].secoes) {
    for (const campo of secao.campos) mapa[campo.nome] = campo.rotulo;
  }
  return mapa;
}

export interface ItemResumo {
  campo: string;
  rotulo: string;
  /** Ocupa a linha inteira da grade — para respostas longas. */
  largo?: boolean;
}

/*
  Resumo que o painel mostra ao abrir uma triagem.

  Os rótulos são curtos de propósito e não repetem os do formulário: o cliente lê
  "Qual é o problema principal?", quem atende lê "Problema relatado". Pergunta e
  cabeçalho de dado têm trabalhos diferentes.

  `nome`, `email`, `telefone` e `criado_em` ficam de fora — aparecem no cabeçalho
  do card, não na grade.
*/
export const RESUMO_ADMIN: Record<Servico, ItemResumo[]> = {
  suporte: [
    { campo: 'problema', rotulo: 'Problema relatado' },
    { campo: 'quando', rotulo: 'Quando começou' },
    { campo: 'causa', rotulo: 'Causa suspeita' },
    { campo: 'tentou', rotulo: 'Já tentou resolver' },
    { campo: 'sistema', rotulo: 'Sistema operacional' },
    { campo: 'idade', rotulo: 'Idade do equipamento' },
    { campo: 'armazenamento', rotulo: 'Armazenamento' },
    { campo: 'ram', rotulo: 'Memória RAM' },
    { campo: 'tem_backup', rotulo: 'Tem backup' },
    { campo: 'programas', rotulo: 'Programas essenciais' },
    { campo: 'modalidade', rotulo: 'Modalidade' },
    { campo: 'observacoes', rotulo: 'Observações', largo: true },
  ],
  seguranca: [
    { campo: 'perfil', rotulo: 'Perfil de uso' },
    { campo: 'dispositivos', rotulo: 'Dispositivos' },
    { campo: 'servicos', rotulo: 'Serviços/contas importantes' },
    { campo: 'preocupacao', rotulo: 'Preocupação principal', largo: true },
    { campo: 'incidente', rotulo: 'Já teve incidente' },
    { campo: 'incidente_desc', rotulo: 'Descrição do incidente' },
    { campo: 'usa_2fa', rotulo: 'Usa 2FA' },
    { campo: 'usa_gerenciador', rotulo: 'Usa gerenciador de senhas' },
    { campo: 'tem_backup', rotulo: 'Faz backup' },
    { campo: 'modalidade', rotulo: 'Modalidade' },
    { campo: 'observacoes', rotulo: 'Observações', largo: true },
  ],
  desenvolvimento: [
    { campo: 'tipo_cliente', rotulo: 'Tipo de cliente' },
    { campo: 'tipo_projeto', rotulo: 'Tipo de projeto' },
    { campo: 'descricao', rotulo: 'Descrição do projeto', largo: true },
    { campo: 'tem_referencia', rotulo: 'Tem referência' },
    { campo: 'referencia_url', rotulo: 'Referência' },
    { campo: 'prazo', rotulo: 'Prazo desejado' },
    { campo: 'orcamento', rotulo: 'Faixa de orçamento' },
    { campo: 'ja_tem_algo', rotulo: 'Já tem algo construído' },
    { campo: 'ja_tem_desc', rotulo: 'Descrição do existente' },
    { campo: 'stack_preferida', rotulo: 'Stack preferida' },
    { campo: 'observacoes', rotulo: 'Observações', largo: true },
  ],
};

