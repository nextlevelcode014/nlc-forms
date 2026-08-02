from pydantic import BaseModel


# Contato não chega mais por aqui: o cliente é cadastrado antes de o link
# existir, e o token carrega o cliente_id. O formulário só pergunta o que é do
# atendimento. Correção de telefone acontece no acompanhamento.
#
# O `extra` do Pydantic segue no padrão (ignorar), e isso importa: link já
# enviado a cliente aponta para a versão antiga do formulário, que ainda manda
# nome e telefone no corpo. Eles são descartados em silêncio em vez de virarem
# 422 — o link continua funcionando até o deploy alcançar o navegador dele.
class TriagemSuporte(BaseModel):
    problema: str
    quando: str
    causa: str = ""
    tentou: str = ""
    marca: str
    modelo: str = ""
    sistema: str
    idade: str = ""
    armazenamento: str = ""
    ram: str = ""
    tem_backup: str
    programas: str
    modalidade: str
    observacoes: str = ""


class TriagemSeguranca(BaseModel):
    perfil: str
    dispositivos: str
    servicos: str
    preocupacao: str
    incidente: str
    incidente_desc: str = ""
    usa_2fa: str
    usa_gerenciador: str
    tem_backup: str
    modalidade: str
    observacoes: str = ""


class TriagemDesenvolvimento(BaseModel):
    tipo_cliente: str
    tipo_projeto: str
    descricao: str
    tem_referencia: str
    referencia_url: str = ""
    prazo: str
    orcamento: str
    ja_tem_algo: str
    ja_tem_desc: str = ""
    stack_preferida: str = ""
    observacoes: str = ""


class ClienteRequest(BaseModel):
    """A pasta. Criada por você, antes de qualquer formulário."""

    nome: str
    email: str
    telefone: str = ""
    notas: str = ""


class GerarTokenRequest(BaseModel):
    # O token carrega o cliente: é isto que faz a triagem cair na pasta certa
    # mesmo que o cliente digite o e-mail errado no formulário.
    cliente_id: int
    servico: str
    nota: str = ""
    validade_horas: int | None = None


class ContatoRequest(BaseModel):
    """Correção de contato vinda da página do cliente."""

    telefone: str = ""
    nome: str = ""


class MensagemClienteRequest(BaseModel):
    """Recado do cliente sobre o atendimento — vira evento no histórico."""

    mensagem: str


class ItemOrcamento(BaseModel):
    nome: str
    quantidade: float = 1
    valor_unitario: float


class RelatorioMdRequest(BaseModel):
    """Relatório técnico escrito em Markdown.

    Os campos de metadado são opcionais porque podem vir do frontmatter do
    próprio arquivo; quando preenchidos aqui, sobrescrevem o frontmatter — o
    formulário é a palavra final.
    """

    codigo: str
    markdown: str
    titulo: str = ""
    subtitulo: str = ""
    descricao: str = ""
    versao: str = ""


class SalvarExecucaoRequest(BaseModel):
    codigo: str
    servico: str
    diagnostico: str = ""
    servicos_realizados: str = ""
    recomendacoes: str = ""
    observacoes_internas: str = ""
    itens: list[ItemOrcamento] = []
    data_atendimento: str = ""
    validade_orcamento: str = ""


class EventoRequest(BaseModel):
    """Evento escrito por você na linha do tempo do atendimento.

    O título é livre — não há lista de etapas. Registrar um evento visível é o
    que move o estado do atendimento, porque o estado É o último evento.
    """

    codigo: str
    titulo: str
    detalhe: str = ""
    # False registra para você sem mostrar ao cliente — útil para anotar algo do
    # caso sem transformar em comunicação.
    visivel_cliente: bool = True


