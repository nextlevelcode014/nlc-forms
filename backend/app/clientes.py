"""O cliente como pasta.

A identidade é o e-mail, normalizado na gravação e não só na comparação:
`Fabio@Email.com ` e `fabio@email.com` são a mesma caixa postal, e deixar as
duas entrarem criaria duas pastas para a mesma pessoa — exatamente o que este
modelo existe para evitar.
"""

from fastapi import HTTPException

from app.tempo import agora_iso


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def buscar_por_email(conn, email: str):
    return conn.execute(
        "SELECT * FROM clientes WHERE email = ?", (normalizar_email(email),)
    ).fetchone()


def exigir_cliente(conn, cliente_id: int):
    cliente = conn.execute(
        "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return cliente


def criar(conn, nome: str, email: str, telefone: str = "", notas: str = "") -> int:
    """Cria a pasta. Recusa e-mail repetido em vez de criar uma segunda.

    Aqui o 409 é a resposta certa, e é diferente do que existia antes: não
    bloqueia um cliente de abrir outro atendimento — só diz que essa pasta já
    existe e você deve usá-la.
    """
    email = normalizar_email(email)
    if buscar_por_email(conn, email) is not None:
        raise HTTPException(
            status_code=409, detail="Já existe um cliente com este e-mail."
        )

    agora = agora_iso()
    cursor = conn.execute(
        """
        INSERT INTO clientes (nome, email, telefone, notas, criado_em, atualizado_em)
        VALUES (?,?,?,?,?,?)
        """,
        (nome.strip(), email, telefone.strip(), notas.strip(), agora, agora),
    )
    return cursor.lastrowid


def atualizar_contato(conn, cliente_id: int, nome: str = "", telefone: str = "") -> None:
    """Atualiza só o que veio preenchido.

    O e-mail fica de fora de propósito: ele é a identidade da pasta, e deixar o
    formulário público reescrevê-lo permitiria mover o histórico de uma pessoa
    para outra caixa postal com um campo de texto.
    """
    campos, valores = [], []
    if nome.strip():
        campos.append("nome = ?")
        valores.append(nome.strip())
    if telefone.strip():
        campos.append("telefone = ?")
        valores.append(telefone.strip())

    if not campos:
        return

    campos.append("atualizado_em = ?")
    valores.extend([agora_iso(), cliente_id])
    conn.execute(f"UPDATE clientes SET {', '.join(campos)} WHERE id = ?", valores)
