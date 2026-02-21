"""
CRM Advocacia — Backend FastAPI com PostgreSQL
Roda localmente em http://localhost:8001
Conecta ao mesmo banco do bot no Railway.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI(title="CRM Advocacia")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# URL pública do PostgreSQL (substitua pela sua DATABASE_PUBLIC_URL do Railway)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "COLE_AQUI_SUA_DATABASE_PUBLIC_URL"
)


def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            cpf TEXT UNIQUE NOT NULL,
            telefone TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agendamentos (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id),
            data_consulta TEXT NOT NULL,
            hora_consulta TEXT NOT NULL,
            tipo_consulta TEXT NOT NULL,
            status TEXT DEFAULT 'ativo',
            observacoes TEXT,
            criado_em TIMESTAMP DEFAULT NOW(),
            atualizado_em TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversas (
            id SERIAL PRIMARY KEY,
            telefone TEXT NOT NULL,
            origem TEXT NOT NULL DEFAULT 'cliente',
            tipo TEXT DEFAULT 'texto',
            conteudo TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'atendente',
            telefone TEXT,
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id),
            nome TEXT NOT NULL,
            tipo TEXT,
            caminho TEXT NOT NULL,
            tamanho INTEGER,
            criado_em TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS instancias (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            evolution_url TEXT NOT NULL,
            evolution_key TEXT NOT NULL,
            instance_name TEXT NOT NULL,
            status TEXT DEFAULT 'desconectado',
            criado_em TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Banco CRM pronto.", flush=True)

try:
    init_db()
except Exception as e:
    print(f"AVISO: Nao foi possivel conectar ao banco: {e}", flush=True)
    print("Verifique DATABASE_URL no server.py", flush=True)


@app.get("/health")
def health():
    return {"status": "ok"}


# ─── MODELS ──────────────────────────────────────────────

class InstanciaCreate(BaseModel):
    nome: str; evolution_url: str; evolution_key: str; instance_name: str

class UsuarioCreate(BaseModel):
    nome: str; email: str; senha: str; perfil: str = "atendente"; telefone: Optional[str] = None

class ContatoCreate(BaseModel):
    nome: Optional[str] = None; telefone: str; cpf: Optional[str] = None
    email: Optional[str] = None; observacoes: Optional[str] = None

class ContatoUpdate(BaseModel):
    nome: Optional[str] = None; cpf: Optional[str] = None
    email: Optional[str] = None; observacoes: Optional[str] = None

class AgendamentoCreate(BaseModel):
    cliente_id: int; data: str; hora: str
    tipo: str = "primeira_consulta"; observacoes: Optional[str] = None


# ─── INSTÂNCIAS ──────────────────────────────────────────

@app.get("/api/instancias")
def listar_instancias():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM instancias ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close(); return rows

@app.post("/api/instancias")
def criar_instancia(data: InstanciaCreate):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO instancias (nome,evolution_url,evolution_key,instance_name) VALUES (%s,%s,%s,%s)",
        (data.nome, data.evolution_url, data.evolution_key, data.instance_name))
    conn.commit(); cur.close(); conn.close(); return {"ok": True}

@app.delete("/api/instancias/{id}")
def deletar_instancia(id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM instancias WHERE id=%s", (id,))
    conn.commit(); cur.close(); conn.close(); return {"ok": True}

@app.get("/api/instancias/{id}/status")
def status_instancia(id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM instancias WHERE id=%s", (id,))
    row = cur.fetchone()
    if not row: raise HTTPException(404)
    r = dict(row)
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{r['evolution_url']}/instance/connectionState/{r['instance_name']}",
                headers={"apikey": r["evolution_key"]})
            estado = resp.json().get("instance", {}).get("state", "unknown")
    except:
        estado = "erro"
    cur.execute("UPDATE instancias SET status=%s WHERE id=%s", (estado, id))
    conn.commit(); cur.close(); conn.close(); return {"status": estado}


# ─── USUÁRIOS ────────────────────────────────────────────

@app.get("/api/usuarios")
def listar_usuarios():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id,nome,email,perfil,telefone,ativo,criado_em FROM usuarios ORDER BY nome")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close(); return rows

@app.post("/api/usuarios")
def criar_usuario(data: UsuarioCreate):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO usuarios (nome,email,senha,perfil,telefone) VALUES (%s,%s,%s,%s,%s)",
            (data.nome, data.email, data.senha, data.perfil, data.telefone))
        conn.commit()
    except psycopg2.IntegrityError:
        raise HTTPException(400, "Email já cadastrado")
    finally:
        cur.close(); conn.close()
    return {"ok": True}

@app.delete("/api/usuarios/{id}")
def deletar_usuario(id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))
    conn.commit(); cur.close(); conn.close(); return {"ok": True}


# ─── CONTATOS ────────────────────────────────────────────

@app.get("/api/contatos")
def listar_contatos(q: Optional[str] = None):
    conn = get_db(); cur = conn.cursor()
    if q:
        cur.execute("SELECT * FROM clientes WHERE nome ILIKE %s OR telefone ILIKE %s OR cpf ILIKE %s ORDER BY nome",
            (f"%{q}%", f"%{q}%", f"%{q}%"))
    else:
        cur.execute("SELECT * FROM clientes ORDER BY nome")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close(); return rows

@app.get("/api/contatos/{id}")
def buscar_contato(id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM clientes WHERE id=%s", (id,))
    row = cur.fetchone()
    if not row: raise HTTPException(404)
    contato = dict(row)
    cur.execute("SELECT * FROM agendamentos WHERE cliente_id=%s ORDER BY data_consulta DESC", (id,))
    contato["agendamentos"] = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM documentos WHERE cliente_id=%s ORDER BY criado_em DESC", (id,))
    contato["documentos"] = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM conversas WHERE telefone=%s ORDER BY criado_em DESC LIMIT 100", (contato["telefone"],))
    contato["conversas"] = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close(); return contato

@app.post("/api/contatos")
def criar_contato(data: ContatoCreate):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO clientes (nome,cpf,telefone) VALUES (%s,%s,%s)",
            (data.nome, data.cpf or "", data.telefone))
        conn.commit()
    except psycopg2.IntegrityError:
        raise HTTPException(400, "CPF ou telefone já cadastrado")
    finally:
        cur.close(); conn.close()
    return {"ok": True}

@app.put("/api/contatos/{id}")
def atualizar_contato(id: int, data: ContatoUpdate):
    conn = get_db(); cur = conn.cursor()
    campos = {k: v for k, v in data.dict().items() if v is not None}
    if campos:
        sets = ", ".join(f"{k}=%s" for k in campos)
        cur.execute(f"UPDATE clientes SET {sets} WHERE id=%s", (*campos.values(), id))
        conn.commit()
    cur.close(); conn.close(); return {"ok": True}

@app.delete("/api/contatos/{id}")
def deletar_contato(id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM clientes WHERE id=%s", (id,))
    conn.commit(); cur.close(); conn.close(); return {"ok": True}


# ─── DOCUMENTOS ──────────────────────────────────────────

@app.post("/api/contatos/{id}/documentos")
async def upload_documento(id: int, file: UploadFile = File(...)):
    destino = UPLOADS_DIR / f"{id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    conteudo = await file.read()
    destino.write_bytes(conteudo)
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO documentos (cliente_id,nome,tipo,caminho,tamanho) VALUES (%s,%s,%s,%s,%s)",
        (id, file.filename, file.content_type, str(destino), len(conteudo)))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True, "nome": file.filename}

@app.delete("/api/documentos/{id}")
def deletar_documento(id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT caminho FROM documentos WHERE id=%s", (id,))
    row = cur.fetchone()
    if row:
        try: Path(row["caminho"]).unlink()
        except: pass
        cur.execute("DELETE FROM documentos WHERE id=%s", (id,))
        conn.commit()
    cur.close(); conn.close(); return {"ok": True}


# ─── AGENDAMENTOS ────────────────────────────────────────

@app.get("/api/agendamentos")
def listar_agendamentos():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT a.*, c.nome as contato_nome, c.telefone as contato_telefone
        FROM agendamentos a LEFT JOIN clientes c ON a.cliente_id = c.id
        ORDER BY a.data_consulta DESC, a.hora_consulta DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close(); return rows

@app.post("/api/agendamentos")
def criar_agendamento(data: AgendamentoCreate):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO agendamentos (cliente_id,data_consulta,hora_consulta,tipo_consulta,observacoes) VALUES (%s,%s,%s,%s,%s)",
        (data.cliente_id, data.data, data.hora, data.tipo, data.observacoes))
    conn.commit(); cur.close(); conn.close(); return {"ok": True}

@app.put("/api/agendamentos/{id}/status")
def atualizar_status(id: int, status: str):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE agendamentos SET status=%s, atualizado_em=NOW() WHERE id=%s", (status, id))
    conn.commit(); cur.close(); conn.close(); return {"ok": True}

@app.delete("/api/agendamentos/{id}")
def deletar_agendamento(id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM agendamentos WHERE id=%s", (id,))
    conn.commit(); cur.close(); conn.close(); return {"ok": True}


# ─── HISTÓRICO DE CONVERSAS ──────────────────────────────

@app.get("/api/historico/{telefone}")
def historico(telefone: str):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM conversas WHERE telefone=%s ORDER BY criado_em", (telefone,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close(); return rows


# ─── DASHBOARD ───────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as n FROM clientes"); total_contatos = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as n FROM agendamentos WHERE status='ativo'"); total_ag = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as n FROM usuarios WHERE ativo=1"); total_usr = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as n FROM instancias"); total_inst = cur.fetchone()["n"]
    cur.execute("""
        SELECT c.nome, c.telefone, cv.criado_em
        FROM clientes c JOIN conversas cv ON cv.telefone = c.telefone
        ORDER BY cv.criado_em DESC LIMIT 5
    """)
    recentes = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"total_contatos": total_contatos, "total_agendamentos": total_ag,
            "total_usuarios": total_usr, "total_instancias": total_inst, "recentes": recentes}


# ─── STATIC ──────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/")
def index(): return FileResponse(str(BASE_DIR / "static" / "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("api.server:app", host="0.0.0.0", port=port)
