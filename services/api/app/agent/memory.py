from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.agent.schemas import ChatRequest
from app.repository.models import AgentConversation, AgentPreferenceSummary, DeviceUser


class MemoryError(Exception):
    pass


def bounded_session(engine: Engine) -> Session:
    session = Session(engine)
    if engine.dialect.name == "postgresql":
        session.execute(text("SET LOCAL statement_timeout = '3000ms'"))
        session.execute(text("SET LOCAL lock_timeout = '1000ms'"))
    return session


def upsert(session: Session, model: type):
    return (pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert)(model)


@dataclass
class Conversation:
    id: str
    version: int
    messages: list[dict]
    last_seed: str | None
    preference_summary: str


class Memory:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def load(self, request: ChatRequest) -> Conversation:
        with bounded_session(self.engine) as session:
            summary = session.get(AgentPreferenceSummary, request.device_id)
            preference = summary.summary if summary else "尚无音乐偏好反馈。"
            if request.conversation_id:
                row = session.scalar(select(AgentConversation).where(
                    AgentConversation.conversation_id == str(request.conversation_id),
                    AgentConversation.device_id == request.device_id))
                if row is None:
                    raise MemoryError("conversation_not_found")
                return Conversation(row.conversation_id, row.version, row.messages, row.last_seed, preference)
            session.execute(upsert(session, DeviceUser).values(device_id=request.device_id)
                            .on_conflict_do_nothing(index_elements=["device_id"]))
            conversation_id = str(uuid4())
            session.add(AgentConversation(conversation_id=conversation_id, device_id=request.device_id,
                                          messages=[], version=0))
            session.commit()
            return Conversation(conversation_id, 0, [], None, preference)

    def save(self, request: ChatRequest, conversation: Conversation, answer: str) -> None:
        messages = (conversation.messages + [{"role": "user", "content": request.message},
                                             {"role": "assistant", "content": answer}])[-12:]
        with bounded_session(self.engine) as session:
            updated = session.execute(update(AgentConversation).where(
                AgentConversation.conversation_id == conversation.id,
                AgentConversation.device_id == request.device_id,
                AgentConversation.version == conversation.version).values(
                    messages=messages, last_seed=conversation.last_seed,
                    version=conversation.version + 1, updated_at=datetime.now(UTC)))
            if updated.rowcount != 1:
                raise MemoryError("conversation_conflict")
            columns = {"summary": conversation.preference_summary, "updated_at": datetime.now(UTC)}
            session.execute(upsert(session, AgentPreferenceSummary).values(device_id=request.device_id, **columns)
                            .on_conflict_do_update(index_elements=["device_id"], set_=columns))
            session.commit()
