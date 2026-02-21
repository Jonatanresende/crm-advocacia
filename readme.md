# CRM Advocacia — Lex CRM

Sistema de gerenciamento de clientes integrado ao WhatsApp via Evolution API.

## Estrutura

```
crm-advocacia/
├── api/
│   └── server.py       ← Backend FastAPI
├── static/
│   └── index.html      ← Frontend completo
├── uploads/            ← Documentos dos clientes (criado automaticamente)
├── crm.db              ← Banco de dados SQLite (criado automaticamente)
├── requirements.txt
└── instalar.sh
```

## Instalação

### Windows (Cursor terminal)
```bash
pip install -r requirements.txt
```

### Mac/Linux
```bash
chmod +x instalar.sh
./instalar.sh
```

## Iniciar

```bash
cd api
python server.py
```

Acesse: **http://localhost:8001**

## Funcionalidades

### Dashboard
- Total de contatos, agendamentos pendentes, usuários ativos e instâncias

### Contatos
- Cadastrar, buscar, visualizar e excluir contatos
- Ver histórico de agendamentos por contato
- Upload e gestão de documentos por contato

### Agendamentos
- Criar agendamentos manualmente
- Marcar como realizado ou cancelar
- Filtro por status

### Usuários
- Cadastrar advogados, atendentes e admins
- Controle de perfil e status ativo/inativo

### WhatsApp
- Conectar instâncias da Evolution API
- Verificar status de conexão em tempo real
- Gerenciar múltiplos números

## Integração com o Bot

O CRM usa o mesmo banco SQLite do bot (`crm.db`).
Para integrar, copie o `crm.db` para a pasta raiz do bot,
ou aponte o bot para o mesmo arquivo alterando `DB_PATH` no `server.py`.

## Portas

- Bot: http://localhost:8000
- CRM: http://localhost:8001