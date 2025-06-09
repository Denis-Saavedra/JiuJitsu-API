from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
from datetime import date
import bcrypt
import base64
import os
from uuid import uuid4
from firebase_config import db
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# MODELOS
class UsuarioCreate(BaseModel):
    nickname: str
    senha: str
    data_nascimento: str  # formato YYYY-MM-DD
    peso: float
    faixa: str
    graus: int

class UsuarioUpdate(BaseModel):
    peso: Optional[float] = None
    nova_senha: Optional[str] = None
    faixa: Optional[str] = None
    graus: Optional[int] = None
    data_nascimento: Optional[str] = None
    admin: Optional[bool] = None

class Credenciais(BaseModel):
    nickname: str
    senha: str

class Aula(BaseModel):
    uid: str
    data: date
    titulo: str
    faixaEsperada: str

class FotoUpload(BaseModel):
    imagem_base64: str

# ROTAS
@app.get("/")
def read_root():
    return {"message": "API de Aulas de Jiu-Jitsu rodando!"}

@app.post("/usuarios")
def criar_usuario(usuario: UsuarioCreate):
    try:
        existentes = db.collection("usuarios").where("nickname", "==", usuario.nickname).stream()
        if any(existentes):
            raise HTTPException(status_code=400, detail="Nickname já está em uso")

        senha_hash = bcrypt.hashpw(usuario.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        uid = str(uuid4())

        db.collection("usuarios").document(uid).set({
            "uid": uid,
            "nickname": usuario.nickname,
            "senha_hash": senha_hash,
            "data_nascimento": usuario.data_nascimento,
            "peso": usuario.peso,
            "faixa": usuario.faixa,
            "graus": usuario.graus,
            "admin": False
        })

        return {"message": "Usuário criado com sucesso", "uid": uid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
def login_usuario(credenciais: Credenciais):
    try:
        usuarios_ref = db.collection("usuarios").where("nickname", "==", credenciais.nickname).stream()
        usuario_doc = next(usuarios_ref, None)

        if not usuario_doc:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        usuario_data = usuario_doc.to_dict()
        if not bcrypt.checkpw(credenciais.senha.encode('utf-8'), usuario_data["senha_hash"].encode('utf-8')):
            raise HTTPException(status_code=401, detail="Senha incorreta")

        return {
            "uid": usuario_data["uid"],
            "nickname": usuario_data["nickname"],
            "admin": usuario_data.get("admin", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/usuarios/{uid}")
def obter_usuario(uid: str):
    try:
        doc = db.collection("usuarios").document(uid).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        data = doc.to_dict()
        return {
            "nickname": data.get("nickname"),
            "data_nascimento": data.get("data_nascimento"),
            "peso": data.get("peso", 0.0),
            "faixa": data.get("faixa", ""),
            "graus": data.get("graus", 0),
            "admin": data.get("admin", False),
            "fotoURL": data.get("fotoURL")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/usuarios/{uid}")
def atualizar_usuario(uid: str, dados: UsuarioUpdate):
    try:
        doc_ref = db.collection("usuarios").document(uid)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        updates = {}
        if dados.peso is not None:
            updates["peso"] = dados.peso
        if dados.nova_senha:
            updates["senha_hash"] = bcrypt.hashpw(dados.nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        if dados.faixa is not None:
            updates["faixa"] = dados.faixa

        if dados.graus is not None:
            updates["graus"] = dados.graus

        if dados.data_nascimento is not None:
            updates["data_nascimento"] = dados.data_nascimento

        if dados.admin is not None:
            updates["admin"] = dados.admin


        if updates:
            doc_ref.update(updates)

        return {"message": "Dados atualizados com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/usuarios/{uid}/foto")
def upload_foto_local(uid: str, dados: FotoUpload):
    try:
        imagem_bytes = base64.b64decode(dados.imagem_base64)
        doc = db.collection("usuarios").document(uid).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        nickname = doc.to_dict().get("nickname")
        file_path = os.path.join("assets", "usuarios", f"{nickname}.png")

        with open(file_path, "wb") as f:
            f.write(imagem_bytes)

        url_local = f"http://192.168.1.133:8000/assets/usuarios/{nickname}.png"
        db.collection("usuarios").document(uid).update({"fotoURL": url_local})

        return {"message": "Imagem salva localmente", "fotoURL": url_local}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

from typing import Optional

@app.get("/usuarios")
def listar_usuarios(q: Optional[str] = None):
    try:
        usuarios_ref = db.collection("usuarios")

        docs = usuarios_ref.stream()
        resultado = []

        for doc in docs:
            data = doc.to_dict()
            if q:
                if q.lower() not in data.get("nickname", "").lower():
                    continue
            resultado.append({
                "uid": doc.id,  # usa o ID do documento como UID
                "nickname": data.get("nickname"),
                "fotoURL": data.get("fotoURL")
            })

        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
