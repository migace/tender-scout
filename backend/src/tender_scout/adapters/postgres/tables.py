"""The tables the code expects. A test compares them with what the migrations build."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, Date, DateTime, Index, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

metadata = MetaData()

# A notice is read and shown as a whole, so it is kept as one document
# (ADR 0002). The columns beside the document are the ones a query filters or
# sorts by; the document alone is enough to rebuild the notice.
notices = Table(
    "notices",
    metadata,
    # The Base's own id. It stays the same across versions of the notice.
    Column("id", BigInteger, primary_key=True, autoincrement=False),
    Column("number", Text, nullable=False),
    Column("version", BigInteger, nullable=False),
    Column("status", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("buyer_name", Text, nullable=False),
    Column("published_on", Date, nullable=False),
    Column("deadline", DateTime(timezone=True), nullable=False),
    Column("changed_at", DateTime(timezone=True), nullable=False),
    Column("cpv_codes", ARRAY(Text), nullable=False),
    Column("body", JSONB, nullable=False),
    # When this reading was taken from the source. The Base's rules of use ask
    # for it to be shown with the notice.
    Column("read_at", DateTime(timezone=True), nullable=False),
    Index("notices_cpv_codes", "cpv_codes", postgresql_using="gin"),
    Index("notices_deadline", "deadline"),
)
