from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.agent.schemas import AgentRequest
from app.domain.listening import ListeningConstraints
from app.repository.models import (
    AccountConversation,
    AccountPreferenceSummary,
    LoginSession,
)


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
    last_intent: str = "auto"
    constraints: ListeningConstraints = field(default_factory=ListeningConstraints)
    recommendation_context: list[dict] = field(default_factory=list)


class Memory:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def load(self, request: AgentRequest) -> Conversation:
        with bounded_session(self.engine) as session:
            self.check_session(session, request)
            summary = session.get(AccountPreferenceSummary, request.session_id)
            preference = summary.summary if summary else "尚无音乐偏好反馈。"
            if request.conversation_id:
                row = session.scalar(select(AccountConversation).where(
                    AccountConversation.conversation_id == str(request.conversation_id),
                    AccountConversation.user_id == request.user_id,
                    AccountConversation.session_id == request.session_id))
                if row is None:
                    raise MemoryError("conversation_not_found")
                intent = row.messages[-1].get("seed_intent", "auto") if row.messages else "auto"
                state = row.messages[-1] if row.messages else {}
                return Conversation(row.conversation_id, row.version, row.messages, row.last_seed,
                                    preference, intent if intent in ("theme", "song") else "auto",
                                    ListeningConstraints.model_validate(state.get("listening_constraints", {})),
                                    state.get("recommendation_context", [])[:10])
            conversation_id = str(uuid4())
            session.add(AccountConversation(conversation_id=conversation_id, user_id=request.user_id, session_id=request.session_id,
                                          messages=[], version=0))
            session.commit()
            return Conversation(conversation_id, 0, [], None, preference)

    def save(self, request: AgentRequest, conversation: Conversation, answer: str) -> None:
        messages = (conversation.messages + [{"role": "user", "content": request.message},
                                             {"role": "assistant", "content": answer,
                                              "seed_intent": conversation.last_intent,
                                              "listening_constraints": conversation.constraints.model_dump(),
                                              "recommendation_context": conversation.recommendation_context}])[-12:]
        with bounded_session(self.engine) as session:
            self.check_session(session, request)
            updated = session.execute(update(AccountConversation).where(
                AccountConversation.conversation_id == conversation.id,
                AccountConversation.user_id == request.user_id,
                AccountConversation.session_id == request.session_id,
                AccountConversation.version == conversation.version).values(
                    messages=messages, last_seed=conversation.last_seed,
                    version=conversation.version + 1, updated_at=datetime.now(UTC)))
            if updated.rowcount != 1:
                raise MemoryError("conversation_conflict")
            columns = {"summary": conversation.preference_summary, "updated_at": datetime.now(UTC)}
            session.execute(upsert(session, AccountPreferenceSummary).values(user_id=request.user_id, session_id=request.session_id, **columns)
                            .on_conflict_do_update(index_elements=["session_id"], set_=columns))
            session.commit()

    @staticmethod
    def check_session(session: Session, request: AgentRequest) -> None:
        active = session.scalar(select(LoginSession.session_id).where(
            LoginSession.session_id == request.session_id, LoginSession.user_id == request.user_id,
            LoginSession.revoked_at.is_(None), LoginSession.expires_at > datetime.now(UTC)).with_for_update())
        if not active:
            raise MemoryError("conversation_not_found")
