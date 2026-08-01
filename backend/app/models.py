from pydantic import BaseModel


# O contato continua vindo no corpo porque o formulário o mostra pré-preenchido
# e o cliente pode corrigir — mas ele atualiza a ficha do cliente, não vira
# coluna da triagem. Quem diz de quem é a triagem é o cliente_id do token.
class _ComContato(BaseModel):
    nome: str = ""
    telefone: str = ""


class TriagemSuporte(_ComContato):
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


class TriagemSeguranca(_ComContato):
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


class TriagemDesenvolvimento(_ComContato):
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
    status: str = "concluido"
    diagnostico: str = ""
    servicos_realizados: str = ""
    recomendacoes: str = ""
    observacoes_internas: str = ""
    itens: list[ItemOrcamento] = []
    data_atendimento: str = ""
    validade_orcamento: str = ""


class EventoRequest(BaseModel):
    """Evento escrito por você na linha do tempo do atendimento."""

    codigo: str
    # Um dos PASSOS ou "manual". O rótulo do passo aparece para o cliente; o
    # detalhe é o texto livre.
    passo: str = "manual"
    detalhe: str = ""
    # False registra para você sem mostrar ao cliente — útil para anotar algo do
    # caso sem transformar em comunicação.
    visivel_cliente: bool = True
