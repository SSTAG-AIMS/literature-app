# backend/app/models.py

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text, String, ForeignKey, Float
from sqlalchemy.dialects.postgresql import ARRAY

class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    url_pdf: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ✅ pgvector yok, embedding saf float listesi olarak PostgreSQL ARRAY(Float) alanında saklanıyor
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    # ✅ yeni alan: indirilen PDF'in yerel yolu
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # İlişkiler
    authors: Mapped[list["PaperAuthor"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    keywords: Mapped[list["PaperKeyword"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class PaperAuthor(Base):
    __tablename__ = "paper_authors"

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True
    )
    author_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    paper: Mapped["Paper"] = relationship(back_populates="authors")
    author: Mapped["Author"] = relationship()


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(String(255), unique=True)


class PaperKeyword(Base):
    __tablename__ = "paper_keywords"

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    keyword_id: Mapped[int] = mapped_column(
        ForeignKey("keywords.id", ondelete="CASCADE"), primary_key=True
    )

    paper: Mapped["Paper"] = relationship(back_populates="keywords")
    keyword: Mapped["Keyword"] = relationship()
