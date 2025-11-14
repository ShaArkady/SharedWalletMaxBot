from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, Numeric, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())

    owned_wallets: Mapped[List["Wallet"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    wallet_members: Mapped[List["WalletMember"]] = relationship(back_populates="user")
    expenses: Mapped[List["Expense"]] = relationship(back_populates="user")
    incomes: Mapped[List["Income"]] = relationship(back_populates="user")


class Income(Base):
    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())

    # Связи
    wallet: Mapped["Wallet"] = relationship(back_populates="incomes")
    user: Mapped["User"] = relationship(back_populates="incomes")


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())

    owner: Mapped["User"] = relationship(back_populates="owned_wallets")
    members: Mapped[List["WalletMember"]] = relationship(back_populates="wallet", cascade="all, delete-orphan")
    expenses: Mapped[List["Expense"]] = relationship(back_populates="wallet", cascade="all, delete-orphan")
    incomes: Mapped[List["Income"]] = relationship(back_populates="wallet", cascade="all, delete-orphan")


class WalletMember(Base):
    __tablename__ = "wallet_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())

    wallet: Mapped["Wallet"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="wallet_members")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(100))
    destination: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())

    wallet: Mapped["Wallet"] = relationship(back_populates="expenses")
    user: Mapped["User"] = relationship(back_populates="expenses")
