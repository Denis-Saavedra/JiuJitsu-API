from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import List
from datetime import date
import bcrypt
from uuid import uuid4
from firebase_config import db

app = FastAPI()

# 🔸 Rota raiz para teste
@app.get("/")
def read_root():
    return {"message": "API de Aulas de Jiu-Jitsu rodando!"}

# 🔸 Modelo Pydantic para criar usuário
class UsuarioCreate(BaseModel):
    nickname: str
    senha: str
    idade: int
    peso: float
    faixa: str
    graus: int

# 🔸 Cadastro de novo usuário
@app.post("/usuarios")
def criar_usuario(usuario: UsuarioCreate):
    try:
        # Verificar se o nickname já está em uso
        existentes = db.collection("usuarios").where("nickname", "==", usuario.nickname).stream()
        if any(existentes):
            raise HTTPException(status_code=400, detail="Nickname já está em uso")

        senha_hash = bcrypt.hashpw(usuario.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        uid = str(uuid4())

        doc_ref = db.collection("usuarios").document(uid)
        doc_ref.set({
            "uid": uid,
            "nickname": usuario.nickname,
            "senha_hash": senha_hash,
            "idade": usuario.idade,
            "peso": usuario.peso,
            "faixa": usuario.faixa,
            "graus": usuario.graus,
            "admin": False
        })

        return {"message": "Usuário criado com sucesso", "uid": uid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🔸 Login por nickname e senha
class Credenciais(BaseModel):
    nickname: str
    senha: str

@app.post("/login")
def login_usuario(credenciais: Credenciais):
    try:
        usuarios_ref = db.collection("usuarios").where("nickname", "==", credenciais.nickname).stream()
        usuario_doc = next(usuarios_ref, None)

        if not usuario_doc:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        usuario_data = usuario_doc.to_dict()
        senha_correta = bcrypt.checkpw(
            credenciais.senha.encode('utf-8'),
            usuario_data["senha_hash"].encode('utf-8')
        )

        if not senha_correta:
            raise HTTPException(status_code=401, detail="Senha incorreta")

        return {
            "uid": usuario_data["uid"],
            "nickname": usuario_data["nickname"],
            "admin": usuario_data.get("admin", False)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 🔸 Modelo de aula
class Aula(BaseModel):
    uid: str
    data: date
    titulo: str
    faixaEsperada: str

@app.post("/aulas")
def criar_aula(aula: Aula):
    try:
        doc_ref = db.collection("usuarios").document(aula.uid).collection("aulas").document()
        doc_ref.set({
            "data": aula.data.isoformat(),
            "titulo": aula.titulo,
            "faixaEsperada": aula.faixaEsperada
        })
        return {"message": "Aula criada com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/aulas/{uid}")
def listar_aulas(uid: str):
    try:
        aulas_ref = db.collection("usuarios").document(uid).collection("aulas")
        docs = aulas_ref.stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 🔸 Graduacao
@app.get("/graduacao/{uid}")
def consultar_graduacao(uid: str):
    try:
        doc = db.collection("usuarios").document(uid).get()
        if doc.exists:
            return {"faixaEsperada": doc.to_dict().get("faixaEsperada", "")}
        else:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/graduacao/{uid}")
def atualizar_graduacao(uid: str, faixa: str = Body(..., embed=True)):
    try:
        db.collection("usuarios").document(uid).update({"faixaEsperada": faixa})
        return {"message": "Faixa esperada atualizada com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 🔸 Obter dados do usuário (incluindo idade/peso/graus)
@app.get("/usuarios/{uid}")
def obter_usuario(uid: str):
    try:
        doc = db.collection("usuarios").document(uid).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        data = doc.to_dict()
        return {
            "nickname": data.get("nickname"),
            "faixa": data.get("faixa", ""),
            "graus": data.get("graus", 0),
            "idade": data.get("idade", 0),
            "peso": data.get("peso", 0.0),
            "admin": data.get("admin", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
