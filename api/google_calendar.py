"""
api/google_calendar.py
Integração com Google Calendar via Service Account.
"""

import os
import json
import logging
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_service():
    """Cria cliente autenticado do Google Calendar."""
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON não configurada!")
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)


def criar_evento(
    titulo: str,
    data: str,       # formato YYYY-MM-DD
    hora: str,       # formato HH:MM
    descricao: str = "",
    email_convidado: str = None,
    duracao_min: int = 60
) -> str:
    """Cria evento no Google Calendar e retorna o event_id."""
    service = _get_service()

    inicio = datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
    fim = inicio + timedelta(minutes=duracao_min)

    evento = {
        "summary": titulo,
        "description": descricao,
        "start": {"dateTime": inicio.isoformat(), "timeZone": "America/Fortaleza"},
        "end":   {"dateTime": fim.isoformat(),    "timeZone": "America/Fortaleza"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email",  "minutes": 1440},  # 24h antes
                {"method": "popup",  "minutes": 60},    # 1h antes
            ]
        }
    }

    if email_convidado:
        evento["attendees"] = [{"email": email_convidado}]

    result = service.events().insert(calendarId=CALENDAR_ID, body=evento, sendUpdates="all").execute()
    print(f"GOOGLE_CAL: evento criado {result['id']}", flush=True)
    return result["id"]


def atualizar_evento(
    event_id: str,
    data: str = None,
    hora: str = None,
    titulo: str = None,
    descricao: str = None,
    duracao_min: int = 60
) -> bool:
    """Atualiza evento existente no Google Calendar."""
    service = _get_service()

    evento = service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()

    if titulo:
        evento["summary"] = titulo
    if descricao:
        evento["description"] = descricao
    if data and hora:
        inicio = datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
        fim = inicio + timedelta(minutes=duracao_min)
        evento["start"] = {"dateTime": inicio.isoformat(), "timeZone": "America/Fortaleza"}
        evento["end"]   = {"dateTime": fim.isoformat(),    "timeZone": "America/Fortaleza"}

    service.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=evento, sendUpdates="all").execute()
    print(f"GOOGLE_CAL: evento atualizado {event_id}", flush=True)
    return True


def cancelar_evento(event_id: str) -> bool:
    """Remove evento do Google Calendar."""
    service = _get_service()
    service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
    print(f"GOOGLE_CAL: evento removido {event_id}", flush=True)
    return True


def listar_horarios_ocupados(data: str) -> list:
    """
    Retorna lista de horários ocupados em uma data (formato YYYY-MM-DD).
    Usado pelo bot para verificar disponibilidade.
    """
    service = _get_service()

    inicio_dia = datetime.strptime(data, "%Y-%m-%d").replace(hour=0, minute=0)
    fim_dia = inicio_dia.replace(hour=23, minute=59)

    eventos = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=inicio_dia.isoformat() + "-03:00",
        timeMax=fim_dia.isoformat() + "-03:00",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    ocupados = []
    for ev in eventos.get("items", []):
        start = ev.get("start", {}).get("dateTime", "")
        if start:
            hora = datetime.fromisoformat(start).strftime("%H:%M")
            ocupados.append(hora)

    return ocupados


def proximos_slots_disponiveis_calendar(quantidade: int = 5) -> list:
    """
    Retorna próximos horários livres consultando o Google Calendar.
    """
    HORARIOS = ["08:00","09:00","10:00","11:00","13:00","14:00","15:00","16:00"]
    resultado = []
    hoje = datetime.now().date()

    for i in range(30):
        data = hoje + timedelta(days=i)
        # Pular fins de semana
        if data.weekday() >= 5:
            continue
        data_str = data.strftime("%Y-%m-%d")
        ocupados = listar_horarios_ocupados(data_str)
        for hora in HORARIOS:
            if hora not in ocupados:
                resultado.append({"data": data_str, "hora": hora})
                if len(resultado) >= quantidade:
                    return resultado

    return resultado