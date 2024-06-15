from __future__ import annotations

from datetime import date
from typing import Optional

import discord

from pie.database import database, session

from sqlalchemy import (
    BigInteger,
    Integer,
    Boolean,
    String,
    Date,
    Column,
    PrimaryKeyConstraint,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship


class Review(database.base):
    __tablename__ = "school_reviews_reviews"

    id = Column(Integer, primary_key=True)
    discord_id = Column(BigInteger)
    anonym = Column(Boolean, default=True)
    subject = Column(Integer, ForeignKey("school_reviews_subjects.id"))
    subject_object = relationship("Subject")
    tier = Column(Integer, default=0)
    text_review = Column(String, default=None)
    date = Column(Date)
    relevance: list[ReviewRelevance] = relationship(
        "ReviewRelevance", back_populates="review_object", cascade="all, delete"
    )

    @staticmethod
    def get_all(guild: discord.Guild) -> list[Review]:
        return (
            session.query(Review)
            .filter(Review.subject_object.has(guild_id=guild.id))
            .all()
        )

    @staticmethod
    def get(review_id: int) -> Optional[Review]:
        return session.query(Review).filter_by(id=review_id).one_or_none()

    @staticmethod
    def get_for_user(user: discord.User) -> list[Review]:
        return session.query(Review).filter_by(discord_id=user.id).all()

    def vote_up(self, user: discord.User):
        for relevance_review in self.relevance:
            if relevance_review.discord_id == user.id:
                relevance_review.vote = True
                session.commit()
                return
        self.relevance.append(
            ReviewRelevance(discord_id=user.id, vote=True, review=self)
        )
        session.merge(self)
        session.commit()

    def vote_down(self, user: discord.User):
        for relevance_review in self.relevance:
            if relevance_review.discord_id == user.id:
                relevance_review.vote = False
                session.commit()
                return
        self.relevance.append(
            ReviewRelevance(discord_id=user.id, vote=False, review=self)
        )
        session.merge(self)
        session.commit()

    def vote_neutral(self, user: discord.User):
        session.query(ReviewRelevance).filter_by(
            discord_id=user.id, review=self.id
        ).delete()
        session.merge(self)
        session.commit()

    def get_positive_votes(self) -> int:
        return len(list(filter(lambda x: x.vote, self.relevance)))

    def get_negative_votes(self) -> int:
        return len(list(filter(lambda x: not x.vote, self.relevance)))

    @staticmethod
    def add(
        guild: discord.Guild,
        author: discord.User,
        subject_abbreviation: str,
        mark: int,
        anonymous: bool,
        text: str,
    ) -> Optional[Review]:
        subject_object = Subject.get(guild, subject_abbreviation)
        # Prevent race condition
        if subject_object is None:
            return None
        review = (
            session.query(Review)
            .filter(
                Review.subject_object.has(guild_id=guild.id),
                Review.discord_id == author.id,
                Review.subject_object.has(shortcut=subject_abbreviation.lower()),
            )
            .one_or_none()
        )
        if review is not None:
            # Just update the already existing object
            review.mark = mark
            review.anonym = anonymous
            review.text_review = text
            review.date = date.today()
            for relevance_opinion in review.relevance:
                session.delete(relevance_opinion)
        else:
            review = Review(
                discord_id=author.id,
                anonym=anonymous,
                subject=subject_object.id,
                tier=mark,
                text_review=text,
                date=date.today(),
            )
        review.subject_object = subject_object
        session.add(review)
        session.commit()
        return review

    @staticmethod
    def remove(
        guild: discord.Guild, user: discord.User, subject_abbreviation: str
    ) -> bool:
        review = (
            session.query(Review)
            .filter(
                Review.subject_object.has(guild_id=guild.id),
                Review.discord_id == user.id,
                Review.subject_object.has(shortcut=subject_abbreviation.lower()),
            )
            .one_or_none()
        )
        if review is None:
            return False
        session.delete(review)
        session.commit()
        return True


class ReviewRelevance(database.base):
    __tablename__ = "school_reviews_relevance"
    __table_args__ = (PrimaryKeyConstraint("review", "discord_id", name="key"),)

    discord_id = Column(BigInteger)
    vote = Column(Boolean, default=False)
    review = Column(Integer, ForeignKey("school_reviews_reviews.id"))
    review_object = relationship("Review", back_populates="relevance")


class Subject(database.base):
    __tablename__ = "school_reviews_subjects"
    __table_args__ = (UniqueConstraint("shortcut", "guild_id"),)

    id = Column(Integer, primary_key=True)
    shortcut = Column(String)
    guild_id = Column(Integer)
    category = Column(String)
    name = Column(String)
    reviews = relationship(
        "Review", back_populates="subject_object", cascade="all, delete"
    )

    def __repr__(self):
        return (
            f"<Subject id={self.id} shortcut={self.shortcut} "
            f"guild_id={self.guild_id} name={self.name} category={self.category}>"
        )

    def __str__(self):
        return f"{self.shortcut}: {self.name} ({self.category})"

    @staticmethod
    def get(guild: discord.Guild, abbreviation: str) -> Optional[Subject]:
        """Fetch subject from DB. Case-insensitive."""
        return (
            session.query(Subject)
            .filter_by(guild_id=guild.id, shortcut=abbreviation.lower())
            .one_or_none()
        )

    @staticmethod
    def add(guild: discord.Guild, abbreviation: str, name: str, category: str):
        subject = (
            session.query(Subject)
            .filter_by(guild_id=guild.id, shortcut=abbreviation)
            .one_or_none()
        )
        if subject is not None:
            subject.name = name
            subject.category = category
            session.merge(subject)
            session.commit()
            return
        subject = Subject(
            name=name, category=category, shortcut=abbreviation, guild_id=guild.id
        )
        session.add(subject)
        session.commit()

    @staticmethod
    def remove(guild: discord.Guild, abbreviation: str) -> bool:
        return (
            session.query(Subject)
            .filter_by(guild_id=guild.id, shortcut=abbreviation)
            .delete()
            > 0
        )

    @staticmethod
    def get_reviewed(guild: discord.Guild) -> list[Subject]:
        return (
            session.query(Subject)
            .filter(Subject.guild_id == guild.id, Subject.reviews.any())
            .all()
        )

    @staticmethod
    def get_reviewed_by_user(guild: discord.Guild, user: discord.User) -> list[Subject]:
        return (
            session.query(Subject)
            .filter(
                Subject.guild_id == guild.id, Subject.reviews.any(discord_id=user.id)
            )
            .all()
        )
