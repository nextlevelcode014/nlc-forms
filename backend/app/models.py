from pydantic import BaseModel


class TriagemSuporte(BaseModel):
    nome: str
    email: str
    telefone: str = ""
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
    nome: str
    email: str
    telefone: str = ""
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
    nome: str
    email: str
    telefone: str = ""
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


class GerarTokenRequest(BaseModel):
    servico: str
    nota: str = ""
    validade_horas: int | None = None


class ItemOrcamento(BaseModel):
    nome: str
    quantidade: float = 1
    valor_unitario: float


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
